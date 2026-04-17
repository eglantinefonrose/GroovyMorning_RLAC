import os
import glob
import joblib
import pandas as pd
import numpy as np
import argparse
import json
import socket
from datetime import datetime
from tqdm import tqdm
from src.utils import load_transcription, load_timecodes, label_segments
from src.dataset import ChronicleDataset
from evaluate_model_precision import evaluate_model_precision
from transformers import (
    CamembertTokenizer, 
    CamembertForSequenceClassification, 
    Trainer, 
    TrainingArguments
)
import torch
import wandb

# Chemin par défaut du modèle de sortie
OUTPUT_MODEL_DIR = "models/camembert_chronicle"

def train_transformer(srt_files, tc_files, tc_dir_path, model_name="cmarkea/distilcamembert-base", epochs=4, tags=None, max_steps=-1):
    """
    Entraîne un modèle CamemBERT en utilisant toutes les données disponibles.
    Logique d'évaluation supprimée.
    """
    # Détection automatique du matériel
    hardware_info = "CPU"
    if torch.cuda.is_available():
        hardware_info = torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available():
        hardware_info = "Mac Apple Silicon (MPS)"

    # Nom du run explicite pour identification rapide dans WandB
    short_model_name = model_name.split('/')[-1]
    run_name = f"{short_model_name}-{datetime.now().strftime('%d/%m-%H:%M')}"

    # Initialisation de WandB
    wandb.init(
        project="RLAC",
        name=run_name,
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
            "tc_dir": os.path.basename(tc_dir_path),
            "max_steps": max_steps
        }
    )

    print(f"\n--- Initialisation de {model_name} (Run: {run_name}) ---")
    
    tokenizer = CamembertTokenizer.from_pretrained(model_name)
    
    print(f"Préparation du dataset ({len(srt_files)} émissions utilisées pour l'entraînement)...")
    # Utilisation de TOUTES les données pour l'entraînement
    train_dataset = ChronicleDataset(srt_files, tc_files, tokenizer, max_length=128, window_size=2)
    
    # Chargement du modèle avec une tête de classification pour 2 classes (Chronique vs Non-Chronique)
    model = CamembertForSequenceClassification.from_pretrained(model_name, num_labels=2)
    
    # Configuration de l'entraînement (sans validation)
    training_args = TrainingArguments(
        output_dir="./results",
        num_train_epochs=epochs if max_steps <= 0 else 1,
        max_steps=max_steps,
        per_device_train_batch_size=16, 
        warmup_steps=100,
        weight_decay=0.01,
        logging_steps=10, 
        save_strategy="steps",
        save_steps=500, # Moins fréquent puisqu'on ne cherche plus le "meilleur" via validation
        save_total_limit=2, 
        fp16=torch.cuda.is_available(), 
        learning_rate=2e-5,
        report_to="wandb",
        run_name=run_name
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset
    )
    
    print("Début de l'entraînement sémantique intensif (100% data)...")
    trainer.train()
    
    # Sauvegarde
    model.save_pretrained(OUTPUT_MODEL_DIR)
    tokenizer.save_pretrained(OUTPUT_MODEL_DIR)
    print(f"\nModèle sauvegardé avec succès dans {OUTPUT_MODEL_DIR}")

    # --- ÉVALUATION AUTOMATIQUE ---
    if srt_files and tc_files:
        print("\nLancement de l'évaluation automatique sur le premier fichier...")
        # On prend le premier fichier pour l'évaluation
        test_srt = srt_files[0]
        base_name = os.path.basename(test_srt).split('_')[0]
        # Trouver le TC correspondant
        test_tc = next((f for f in tc_files if base_name in f), None)
        
        if test_tc:
            eval_metrics = evaluate_model_precision(test_srt, test_tc)
            # Log des métriques d'évaluation dans WandB avec préfixe rlac-
            wandb.log({
                "rlac-eval/score_global": eval_metrics["score_global"],
                "rlac-eval/cardinality_score": eval_metrics["cardinality_score"],
                "rlac-eval/alignment_score": eval_metrics["alignment_score"],
                "rlac-eval/n_gt": eval_metrics["n_gt"],
                "rlac-eval/n_pred": eval_metrics["n_pred"]
            })
        else:
            print(f"Avertissement : Impossible de trouver le fichier TC pour {test_srt}")

def main():
    # Détermination du BASE_DIR pour les chemins par défaut
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DEFAULT_SRT_DIR = os.path.join(BASE_DIR, "@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo")
    DEFAULT_TC_DIR = os.path.join(BASE_DIR, "@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/2.round3")

    parser = argparse.ArgumentParser(description="Entraînement du détecteur sémantique de chroniques")
    parser.add_argument("--epochs", type=int, default=4, help="Nombre d'époques")
    parser.add_argument("--max_steps", type=int, default=-1, help="Nombre max de pas (écrase les époques si > 0)")
    parser.add_argument("--model", type=str, default="cmarkea/distilcamembert-base", help="Modèle HuggingFace à utiliser")
    parser.add_argument("--tags", type=str, default="", help="Tags séparés par des virgules pour WandB")
    parser.add_argument("--srt_dir", type=str, default=DEFAULT_SRT_DIR, help="Répertoire contenant les fichiers .srt")
    parser.add_argument("--tc_dir", type=str, default=DEFAULT_TC_DIR, help="Répertoire contenant les fichiers de timecodes .txt")
    
    args = parser.parse_args()

    # Transformation de la string des tags en liste
    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]

    os.makedirs("models", exist_ok=True)
    
    srt_files = sorted(glob.glob(os.path.join(args.srt_dir, "*.srt")))
    tc_files = sorted(glob.glob(os.path.join(args.tc_dir, "*.txt")))
    
    if not srt_files or not tc_files:
        print(f"ERREUR : Fichiers 'srt' manquants pour l'entrainement du modèle dans {args.srt_dir}.")
        return

    print(f"Données : {len(srt_files)} émissions trouvées.")
    
    # Lancement de l'entraînement
    train_transformer(srt_files, tc_files, tc_dir_path=args.tc_dir, model_name=args.model, epochs=args.epochs, tags=tags_list, max_steps=args.max_steps)

if __name__ == "__main__":
    main()
