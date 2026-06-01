import os
import argparse
import joblib
import numpy as np
import glob
import re
from sklearn.metrics import accuracy_score, f1_score
from train import RadioChroniqueClassifier
from utils import load_transcription, load_timecodes, label_segments

def find_file_robustly(original_path):
    """Cherche le fichier récursivement dans @assets avec tolérance sur le nom."""
    if os.path.exists(original_path):
        return original_path
        
    filename = os.path.basename(original_path)
    # On essaye aussi de remplacer "transcription_chronique" par "timecode_chronique"
    alt_filename = filename.replace("transcription_chronique", "timecode_chronique")
    
    for depth in ["./", "../", "../../", "../../../", "../../../../"]:
        assets_dir = os.path.join(depth, "@assets")
        if os.path.exists(assets_dir):
            # Recherche récursive
            for fname in [filename, alt_filename]:
                matches = glob.glob(os.path.join(assets_dir, "**", fname), recursive=True)
                if matches:
                    return matches[0]
                    
    return original_path

def evaluate_quality(model_path, config_file="training_config.txt"):
    if not os.path.exists(model_path):
        print(f"Erreur : Le modèle '{model_path}' n'existe pas.")
        return

    print(f"--- Évaluation de Qualité (40/60) pour {model_path} ---")
    
    # 1. Chargement du modèle
    clf = RadioChroniqueClassifier.load_model(model_path)
    
    # 2. Chargement de TOUTES les données de la config
    all_segments = []
    all_labels = []

    if not os.path.exists(config_file):
        print(f"Erreur : Le fichier de config '{config_file}' n'existe pas.")
        return

    with open(config_file, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]

    for line in lines:
        parts = line.split('|')
        if len(parts) < 2: continue
        srt_file = find_file_robustly(parts[0])
        timecodes_file = find_file_robustly(parts[1])
        
        if not os.path.exists(srt_file) or not os.path.exists(timecodes_file):
            print(f"Attention : Fichier manquant pour {os.path.basename(srt_file)} ou {os.path.basename(timecodes_file)}")
            continue

        print(f"Chargement de {os.path.basename(srt_file)}...")
        segments = load_transcription(srt_file)
        timecodes = load_timecodes(timecodes_file)
        labels = label_segments(segments, timecodes)
        
        all_segments.extend(segments)
        all_labels.extend(labels)

    if not all_segments:
        print("Erreur : Aucun segment chargé.")
        return

    y_true_binary = (np.array(all_labels) > 0).astype(int)

    # 3. Prédiction
    print("Extraction des features et prédiction...")
    X = clf.prepare_features(all_segments, training=False)
    y_pred = clf.classifier.predict(X)

    # 4. Calcul des scores (40/60)
    card_score = f1_score(y_true_binary, y_pred) * 100
    align_score = accuracy_score(y_true_binary, y_pred) * 100
    global_score = (card_score * 0.4) + (align_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- La Cardinalité (40%) : {card_score:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {align_score:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", help="Chemin vers le fichier .pkl du modèle")
    parser.add_argument("--config", default="training_config.txt", help="Fichier de config pour les données de test")
    args = parser.parse_args()
    evaluate_quality(args.model_path, args.config)
