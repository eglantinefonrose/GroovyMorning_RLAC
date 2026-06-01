import os
import glob
import torch
import pandas as pd
import numpy as np
from transformers import CamembertTokenizer, CamembertForSequenceClassification, Trainer, TrainingArguments
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import argparse

# --- Configuration par défaut ---
DATA_PATH = "../../../@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
DEFAULT_MODEL = "./camembert_chronicle_start"

class ChronicleDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='binary')
    acc = accuracy_score(labels, preds)
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }

def load_evaluation_data(data_path):
    """Charge les données depuis les dossiers start/end pour l'évaluation."""
    data = []
    # Positifs
    start_dirs = glob.glob(os.path.join(data_path, "**/start_transcription"), recursive=True)
    for d in start_dirs:
        for f in glob.glob(os.path.join(d, "*.txt")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read().replace('\n', ' ').strip()
                    if content: data.append({"text": content[:200], "label": 1})
            except: pass

    # Négatifs
    end_dirs = glob.glob(os.path.join(data_path, "**/end_transcription"), recursive=True)
    for d in end_dirs:
        for f in glob.glob(os.path.join(d, "*.txt")):
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read().replace('\n', ' ').strip()
                    if content: data.append({"text": content[:200], "label": 0})
            except: pass
                
    return pd.DataFrame(data)

def evaluate(model_path, data_path):
    print(f"--- Évaluation du modèle : {model_path} ---")
    
    # 1. Chargement du modèle et tokenizer
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    
    # 2. Chargement des données
    df = load_evaluation_data(data_path)
    if df.empty:
        print("Erreur : Aucune donnée trouvée pour l'évaluation.")
        return

    print(f"Données chargées : {len(df)} échantillons.")

    # 3. Préparation du dataset
    encodings = tokenizer(df['text'].tolist(), truncation=True, padding=True, max_length=128)
    dataset = ChronicleDataset(encodings, df['label'].tolist())

    # 4. Trainer pour l'évaluation
    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir="./tmp_eval", per_device_eval_batch_size=16, report_to="none"),
        compute_metrics=compute_metrics
    )

    # 5. Calcul des métriques
    results = trainer.evaluate(eval_dataset=dataset)
    
    # 6. Calcul de la Note de Qualité (Format standardisé)
    card_score = results.get('eval_f1', 0) * 100
    align_score = results.get('eval_accuracy', 0) * 100
    global_score = (card_score * 0.4) + (align_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- La Cardinalité (40%) : {card_score:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {align_score:.1f}%")
    print("-" * 40)
    print(f"Détails : F1={results['eval_f1']:.4f}, Acc={results['eval_accuracy']:.4f}")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue un modèle CamemBERT existant sans ré-entraînement.")
    parser.add_argument("model_path", help="Chemin local ou ID Hugging Face du modèle.")
    parser.add_argument("--data", default=DATA_PATH, help="Chemin vers le dossier assets contenant les transcriptions.")
    
    args = parser.parse_args()
    evaluate(args.model_path, args.data)
