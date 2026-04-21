import os
import re
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from tqdm import tqdm
from typing import List, Dict
import warnings

warnings.filterwarnings('ignore')

from utils import load_transcription, load_timecodes, label_segments, extract_features_from_text


class RadioChroniqueClassifier:
    def __init__(self, window_size=2):
        self.use_bert = False # Désactivé pour la version RF simple
        self.window_size = window_size
        self.classifier = None
        self.tfidf_vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 3))
        self.scaler = StandardScaler()

    def prepare_features(self, segments: List[Dict], training: bool = False) -> np.ndarray:
        """Prépare les features pour tous les segments avec fenêtre glissante"""
        texts_for_tfidf = [re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', seg['text']).strip() for seg in segments]

        # 1. Extraction des features de base
        base_features = []
        for seg in tqdm(segments, desc="Extraction features de base", leave=False):
            text_features = extract_features_from_text(seg['text'])
            base_features.append([
                seg['start'],
                seg['end'],
                seg['end'] - seg['start'],
                text_features['word_count'],
                text_features['char_count'],
                text_features['has_punctuation'],
                text_features['has_question_mark'],
                text_features['has_exclamation'],
                text_features['avg_word_length'],
                text_features['time_of_day'],
                text_features['has_jingle']
            ])
        base_features = np.array(base_features)

        # 2. Features TF-IDF
        if training:
            tfidf_features = self.tfidf_vectorizer.fit_transform(texts_for_tfidf).toarray()
        else:
            tfidf_features = self.tfidf_vectorizer.transform(texts_for_tfidf).toarray()

        all_features = np.hstack([base_features, tfidf_features])

        # 3. Application de la fenêtre glissante
        if self.window_size > 0:
            sequential_features = []
            num_segments = len(all_features)
            feature_dim = all_features.shape[1]
            
            for i in range(num_segments):
                window = []
                for j in range(i - self.window_size, i + self.window_size + 1):
                    if j < 0 or j >= num_segments:
                        window.append(np.zeros(feature_dim))
                    else:
                        window.append(all_features[j])
                sequential_features.append(np.concatenate(window))
            final_features = np.array(sequential_features)
        else:
            final_features = all_features

        # 4. Normalisation
        if training:
            final_features = self.scaler.fit_transform(final_features)
        else:
            final_features = self.scaler.transform(final_features)

        return final_features

    def train_from_config(self, config_files: List[str], output_model_path: str):
        """Entraîne le modèle à partir de fichiers de configuration"""
        all_segments = []
        all_labels = []

        for config_file in config_files:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_line = f.read().strip()
            parts = config_line.split('|')
            srt_file, timecodes_file = parts[0], parts[1]
            
            segments = load_transcription(srt_file)
            timecodes = load_timecodes(timecodes_file)
            labels = label_segments(segments, timecodes)
            
            all_segments.extend(segments)
            all_labels.extend(labels)

        print(f"Total: {len(all_segments)} segments, {sum(1 for l in all_labels if l > 0)} segments de chroniques")
        
        if not all_segments:
            print("Erreur: Aucun segment n'a été chargé. Vérifiez vos fichiers SRT et la configuration.")
            return

        X = self.prepare_features(all_segments, training=True)
        y = np.array(all_labels)
        # Pour RF simple, on simplifie les labels 1 et 2 en 1 (Chronique)
        y_binary = (y > 0).astype(int)

        X_train, X_test, y_train, y_test = train_test_split(X, y_binary, test_size=0.2, random_state=42)
        
        self.classifier = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        self.classifier.fit(X_train, y_train)

        y_pred = self.classifier.predict(X_test)
        print("\n=== Évaluation Random Forest ===")
        print(classification_report(y_test, y_pred))

        self.save_model(output_model_path)

    def save_model(self, model_path: str):
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        model_data = {
            'classifier': self.classifier,
            'tfidf_vectorizer': self.tfidf_vectorizer,
            'scaler': self.scaler,
            'use_bert': False,
            'window_size': self.window_size
        }
        joblib.dump(model_data, model_path)
        print(f"Modèle sauvegardé: {model_path}")

    @staticmethod
    def load_model(model_path: str):
        model_data = joblib.load(model_path)
        classifier = RadioChroniqueClassifier(window_size=model_data.get('window_size', 0))
        classifier.classifier = model_data['classifier']
        classifier.tfidf_vectorizer = model_data['tfidf_vectorizer']
        classifier.scaler = model_data['scaler']
        return classifier


if __name__ == "__main__":
    config_files = ["training_config.txt"]
    model = RadioChroniqueClassifier(window_size=2)
    model.train_from_config(config_files, "models/radio_chronique_rf.pkl")
