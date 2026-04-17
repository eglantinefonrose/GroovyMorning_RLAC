import os
import glob
import joblib
import pandas as pd
import numpy as np
import argparse
import json
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from tqdm import tqdm
from src.utils import load_transcription, load_timecodes, label_segments
from src.dataset import ChronicleDataset
from transformers import (
    CamembertTokenizer, 
    CamembertForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback
)
import torch
import wandb
import socket

# Configuration des chemins
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRT_DIR = os.path.join(BASE_DIR, "@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo")
TC_DIR = os.path.join(BASE_DIR, "@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/2.round3")
OUTPUT_MODEL_DIR = "models/camembert_chronicle"

def train_transformer(srt_files, tc_files, model_name="cmarkea/distilcamembert-base", epochs=4, tags=None):
    """
    Entraîne un modèle CamemBERT avec monitoring complet.
    """
    # Détection automatique du matériel
    hardware_info = "CPU"
    if torch.cuda.is_available():
        hardware_info = torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available():
        hardware_info = "Mac Apple Silicon (MPS)"

    # Initialisation de WandB avec Config enrichie et Tags
    wandb.init(
        project="RLAC",
        tags=tags if tags else [],
        config={
            "model_architecture": "CamemBERT",
            "model_variant": model_name,
            "is_distilled": "distil" in model_name.lower(),
            "epochs": epochs,
            "batch_size": 16,
            "max_length": 128,
            "learning_rate": 2e-5,
            "dataset_size": len(srt_files),
            "machine": socket.gethostname(),
            "hardware": hardware_info,
            "tc_dir": os.path.basename(TC_DIR) # Pour savoir quelle version des timecodes on utilise
        }
    )

    print(f"\n--- Initialisation de {model_name} (Version Distillée Rapide) ---")
    
    tokenizer = CamembertTokenizer.from_pretrained(model_name)
    
    # Séparation au niveau des fichiers (émissions) pour éviter les fuites de données
    train_srt, val_srt = train_test_split(srt_files, test_size=0.15, random_state=42)
    
    print(f"Préparation du dataset (Train: {len(train_srt)}, Val: {len(val_srt)} emissions)...")
    # max_length réduit à 128 pour doubler la vitesse d'entraînement
    train_dataset = ChronicleDataset(train_srt, tc_files, tokenizer, max_length=128, window_size=2)
    val_dataset = ChronicleDataset(val_srt, tc_files, tokenizer, max_length=128, window_size=2)
    
    # Chargement du modèle avec une tête de classification pour 2 classes (Chronique vs Non-Chronique)
    model = CamembertForSequenceClassification.from_pretrained(model_name, num_labels=2)
    
    # Configuration de l'entraînement
    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=epochs,
        per_device_train_batch_size=16, # Augmenté pour plus de rapidité
        per_device_eval_batch_size=16,
        warmup_steps=100,
        weight_decay=0.01,
        logging_steps=10, # Plus fréquent pour WandB
        eval_strategy="steps", 
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2, # Garde seulement les 2 meilleurs/derniers checkpoints pour économiser l'espace
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        fp16=torch.cuda.is_available(), 
        learning_rate=2e-5,
        report_to="wandb", # Envoi des logs à WandB
        run_name=f"train-{model_name.split('/')[-1]}"
    )
    
    def compute_metrics(pred):
        labels = pred.label_ids
        preds = pred.predictions.argmax(-1)
        # On utilise le F1-score pondéré pour gérer le déséquilibre des classes
        f1 = f1_score(labels, preds, average='weighted')
        return {'f1': f1}

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )
    
    print("Début de l'entraînement sémantique (Fine-tuning CamemBERT)...")
    trainer.train()
    
    # Évaluation finale détaillée
    print("\nÉvaluation finale sur l'ensemble de validation...")
    predictions = trainer.predict(val_dataset)
    y_pred = predictions.predictions.argmax(-1)
    y_true = predictions.label_ids
    
    print("\nRapport de classification sémantique :")
    print(classification_report(y_true, y_pred, target_names=["Silence/Bruit", "Chronique"]))
    
    # Sauvegarde
    model.save_pretrained(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print(f"\nModèle sémantique sauvegardé dans {OUTPUT_MODEL_DIR}")

def main():
    parser = argparse.ArgumentParser(description="Entraînement du détecteur sémantique de chroniques")
    parser.add_argument("--epochs", type=int, default=4, help="Nombre d'époques d'entraînement")
    args = parser.parse_args()

    os.makedirs("models", exist_ok=True)
    srt_files = sorted(glob.glob(os.path.join(SRT_DIR, "*.srt")))
    tc_files = sorted(glob.glob(os.path.join(TC_DIR, "*.txt")))
    
    if not srt_files or not tc_files:
        print("ERREUR : Fichiers manquants.")
        return

    print(f"Données : {len(srt_files)} émissions trouvées.")
    
    # Lancement direct du modèle sémantique
    train_transformer(srt_files, tc_files, epochs=args.epochs)

if __name__ == "__main__":
    main()
