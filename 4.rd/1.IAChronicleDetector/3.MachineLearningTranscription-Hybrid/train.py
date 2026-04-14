import os
import re
import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from tqdm import tqdm
from typing import List, Dict
import warnings

# Gestion de l'import CRF (souvent problématique selon l'install)
try:
    from torchcrf import CRF
except ImportError:
    from crf import CRF

warnings.filterwarnings('ignore')

from utils import load_transcription, load_timecodes, label_segments, extract_features_from_text


class RadioChroniqueClassifier:
    """Extracteur de features BERT + TF-IDF + Base"""
    def __init__(self, window_size=0):
        self.use_bert = True
        self.window_size = window_size
        print("Chargement de CamemBERT...")
        self.tokenizer = AutoTokenizer.from_pretrained("camembert-base")
        self.bert_model = AutoModel.from_pretrained("camembert-base")
        
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
        elif torch.backends.mps.is_available():
            self.device = torch.device('mps')
        else:
            self.device = torch.device('cpu')
            
        print(f"Utilisation du device: {self.device}")
        self.bert_model.to(self.device)
        self.bert_model.eval()
        
        self.tfidf_vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 3))
        self.scaler = StandardScaler()

    def get_bert_embeddings_batch(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        all_embeddings = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Extraction BERT", leave=False):
            batch_texts = [t if t and len(t.strip()) > 0 else " " for t in texts[i:i+batch_size]]
            inputs = self.tokenizer(batch_texts, return_tensors='pt', truncation=True, max_length=128, padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.bert_model(**inputs)
                embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                all_embeddings.append(embeddings)
        return np.vstack(all_embeddings)

    def prepare_features(self, segments: List[Dict], training: bool = False) -> np.ndarray:
        texts_for_bert = [re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', seg['text']).strip() for seg in segments]

        base_features = []
        for seg in tqdm(segments, desc="Features de base", leave=False):
            tf = extract_features_from_text(seg['text'])
            base_features.append([seg['start'], seg['end'], seg['end']-seg['start'], tf['word_count'], 
                                 tf['char_count'], tf['has_punctuation'], tf['has_question_mark'], 
                                 tf['has_exclamation'], tf['avg_word_length'], tf['time_of_day'], tf['has_jingle']])
        base_features = np.array(base_features)

        if training:
            tfidf_features = self.tfidf_vectorizer.fit_transform(texts_for_bert).toarray()
        else:
            tfidf_features = self.tfidf_vectorizer.transform(texts_for_bert).toarray()

        bert_features = self.get_bert_embeddings_batch(texts_for_bert)
        all_features = np.hstack([base_features, tfidf_features, bert_features])

        if training:
            all_features = self.scaler.fit_transform(all_features)
        else:
            all_features = self.scaler.transform(all_features)

        return all_features

    def save_model(self, model_path: str):
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump({'tfidf_vectorizer': self.tfidf_vectorizer, 'scaler': self.scaler, 'use_bert': True, 'window_size': 0}, model_path)

    @staticmethod
    def load_model(model_path: str):
        model_data = joblib.load(model_path)
        instance = RadioChroniqueClassifier(window_size=0)
        instance.tfidf_vectorizer = model_data['tfidf_vectorizer']
        instance.scaler = model_data['scaler']
        return instance


class FocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0):
        super(FocalLoss, self).__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction='none', weight=self.alpha)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma * ce_loss)
        return focal_loss.mean()


class SequenceDataset(Dataset):
    def __init__(self, features, labels, seq_len=30):
        self.features = torch.FloatTensor(features)
        self.labels = torch.LongTensor(labels)
        self.seq_len = seq_len
        
    def __len__(self):
        return len(self.features) - self.seq_len + 1
        
    def __getitem__(self, idx):
        return self.features[idx:idx+self.seq_len], self.labels[idx:idx+self.seq_len]


class ChroniqueLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=128):
        super(ChroniqueLSTM, self).__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers=2, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_dim * 2, 3) # 0=Hors, 1=Start, 2=Inside
        self.dropout = nn.Dropout(0.2)
        self.crf = CRF(3, batch_first=True)

    def forward(self, x, tags=None):
        lstm_out, _ = self.lstm(x)
        emissions = self.fc(self.dropout(lstm_out))
        if tags is not None:
            return -self.crf(emissions, tags, reduction='mean'), emissions
        return self.crf.decode(emissions)


class HybridSequenceClassifier:
    def __init__(self, input_dim, seq_len=30):
        self.device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))
        self.model = ChroniqueLSTM(input_dim).to(self.device)
        self.seq_len = seq_len
        self.input_dim = input_dim

    def train_model(self, X, y, epochs=15):
        dataset = SequenceDataset(X, y, self.seq_len)
        loader = DataLoader(dataset, batch_size=16, shuffle=True)
        weights = torch.FloatTensor([1.0, 5.0, 2.0]).to(self.device)
        focal_criterion = FocalLoss(alpha=weights)
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for bx, by in loader:
                bx, by = bx.to(self.device), by.to(self.device)
                optimizer.zero_grad()
                crf_loss, emissions = self.model(bx, by)
                f_loss = focal_criterion(emissions.view(-1, 3), by.view(-1))
                loss = crf_loss + f_loss
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(loader):.4f}")

    def predict(self, X):
        self.model.eval()
        with torch.no_grad():
            x_tensor = torch.FloatTensor(X).unsqueeze(0).to(self.device)
            best_sequence = self.model(x_tensor)[0]
            probs = np.zeros((len(best_sequence), 3))
            for i, label in enumerate(best_sequence):
                probs[i, label] = 1.0
        return probs

    def save(self, path):
        torch.save({'model_state_dict': self.model.state_dict(), 'input_dim': self.input_dim, 'seq_len': self.seq_len}, path)

    @staticmethod
    def load(path):
        cp = torch.load(path)
        inst = HybridSequenceClassifier(cp['input_dim'], seq_len=cp['seq_len'])
        inst.model.load_state_dict(cp['model_state_dict'])
        return inst


if __name__ == "__main__":
    # Chargement données
    config_files = ["training_config.txt"]
    all_segments, all_labels = [], []
    for cf in config_files:
        with open(cf, 'r', encoding='utf-8') as f:
            line = f.read().strip()
        parts = line.split('|')
        segments = load_transcription(parts[0])
        all_segments.extend(segments)
        all_labels.extend(label_segments(segments, load_timecodes(parts[1])))

    print(f"Entraînement hybride sur {len(all_segments)} segments...")
    
    if not all_segments:
        print("Erreur: Aucun segment n'a été chargé. Vérifiez vos fichiers SRT et la configuration.")
        exit(1)

    base_extractor = RadioChroniqueClassifier()
    X = base_extractor.prepare_features(all_segments, training=True)
    y = np.array(all_labels)

    hybrid_model = HybridSequenceClassifier(input_dim=X.shape[1])
    hybrid_model.train_model(X, y, epochs=15)

    base_extractor.save_model("models/radio_chronique_hybrid_base.pkl")
    hybrid_model.save("models/radio_chronique_hybrid_hybrid.pt")
    print("Modèles sauvegardés dans models/")
