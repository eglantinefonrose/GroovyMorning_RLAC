import os
import argparse
import torch
import pandas as pd
import glob
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from src.utils import load_transcription, load_timecodes
from src.evaluation import evaluate_chronicles

def find_file_robustly(original_path):
    """Cherche le fichier récursivement dans @assets avec tolérance."""
    if os.path.exists(original_path):
        return original_path
    filename = os.path.basename(original_path)
    alt_filename = filename.replace("transcription_chronique", "timecode_chronique").replace("timecode_chronique", "transcription_chronique")
    for depth in ["./", "../", "../../", "../../../", "../../../../"]:
        assets_dir = os.path.join(depth, "@assets")
        if os.path.exists(assets_dir):
            for fname in [filename, alt_filename]:
                matches = glob.glob(os.path.join(assets_dir, "**", fname), recursive=True)
                if matches: return matches[0]
    return original_path

def evaluate_quality(model_path, srt_path, tc_path):
    if not os.path.exists(model_path):
        print(f"Erreur : Le modèle '{model_path}' n'existe pas.")
        return

    srt_path = find_file_robustly(srt_path)
    tc_path = find_file_robustly(tc_path)

    print(f"--- Évaluation de Qualité (40/60) pour {model_path} ---")
    
    # 1. Prédire (Réimplémentation légère pour flexibilité)
    import predict as pred_mod
    original_path = pred_mod.MODEL_PATH
    pred_mod.MODEL_PATH = model_path
    try:
        predicted_chronicles = pred_mod.predict(srt_path)
    finally:
        pred_mod.MODEL_PATH = original_path

    if predicted_chronicles is None: predicted_chronicles = []

    # 2. Charger la vérité terrain
    ground_truth = load_timecodes(tc_path)
    
    # 3. Calculer les métriques
    metrics = evaluate_chronicles(predicted_chronicles, ground_truth)
    
    card_score = metrics['cardinality_score'] * 100
    align_score = metrics['alignment_score'] * 100
    global_score = (card_score * 0.4) + (align_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- La Cardinalité (40%) : {card_score:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {align_score:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path")
    parser.add_argument("srt_path")
    parser.add_argument("tc_path")
    args = parser.parse_args()
    evaluate_quality(args.model_path, args.srt_path, args.tc_path)
