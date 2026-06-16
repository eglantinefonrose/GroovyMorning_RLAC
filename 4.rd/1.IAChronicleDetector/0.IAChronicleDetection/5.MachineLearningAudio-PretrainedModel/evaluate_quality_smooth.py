import os
import argparse
import json
import sys
import numpy as np
import torch

# Ajout du dossier src au path pour les imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from predict_smooth import predict_smooth

def parse_time(time_str):
    """
    Parses time strings in various formats:
    - HH:MM:SS.mmm
    - HH:MM:SS
    - MM:SS
    - SSSS.sss (raw seconds)
    """
    if isinstance(time_str, (int, float)):
        return float(time_str)
    
    try:
        if ':' not in time_str:
            return float(time_str)
        
        parts = time_str.split(':')
        if len(parts) == 3: # HH:MM:SS[.mmm]
            h, m, s = parts
        elif len(parts) == 2: # MM:SS[.mmm]
            h = 0
            m, s = parts
        else:
            return 0.0

        if '.' in s:
            s, ms = s.split('.')
            ms = float("0." + ms)
        else:
            ms = 0.0
            
        return int(h) * 3600 + int(m) * 60 + int(s) + ms
    except Exception as e:
        print(f"Warning: Could not parse time '{time_str}': {e}")
        return 0.0

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def evaluate_quality(model_type, model_dir, audio_path, tc_path, threshold=0.5, smooth_window=5, window_size=10.0, overlap=5.0):
    print(f"--- Évaluation de Qualité (Smooth) ---")
    print(f"Modèle: {model_type} ({model_dir if model_dir else 'Défaut'})")
    print(f"Audio: {audio_path}")
    print(f"Vérité terrain: {tc_path}")
    print(f"Paramètres: Seuil={threshold}, Lissage={smooth_window}, Fenêtre={window_size}, Overlap={overlap}")
    
    # 1. Prédire
    print("\nLancement de l'inférence...")
    predictions = predict_smooth(
        audio_path=audio_path,
        model_type=model_type,
        model_dir=model_dir,
        threshold=threshold,
        smooth_window=smooth_window,
        window_size=window_size,
        overlap=overlap
    )
    
    pred_intervals = [(parse_time(p['start']), parse_time(p['end'])) for p in predictions]

    # 2. Charger la vérité terrain
    gt_intervals = []
    if os.path.exists(tc_path):
        with open(tc_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '|' not in line:
                    continue
                start_str, end_str = line.split('|')
                gt_intervals.append((parse_time(start_str), parse_time(end_str)))
    else:
        print(f"Erreur: Fichier de vérité terrain non trouvé: {tc_path}")
        return

    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    
    print(f"\nNombre de chroniques : GT={n_gt}, Pred={n_pred}")

    # 3. Calculer les métriques
    # Cardinalité : Score basé sur la différence du nombre de segments détectés
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    
    # Alignement temporel et IoU
    iou_scores = []
    matched_gt = set()
    pred_used = set()
    
    for i, p in enumerate(pred_intervals):
        best_iou = 0
        best_gt_idx = -1
        for j, gt in enumerate(gt_intervals):
            # On ne match un segment GT qu'une seule fois pour le calcul strict, 
            # mais ici on veut surtout voir la qualité de l'alignement
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = j
        
        if best_gt_idx != -1 and best_iou > 0:
            iou_scores.append(best_iou)
            matched_gt.add(best_gt_idx)
            pred_used.add(i)

    # Précision, Rappel, F1 basés sur IoU > 0.0 (segments qui touchent au moins un GT)
    # Pour un F1 plus "dur", on pourrait filtrer IoU > 0.3 ou 0.5
    mean_iou = np.mean(iou_scores) if iou_scores else 0.0
    
    # Couverture (Recall du point de vue des segments GT)
    recall = len(matched_gt) / n_gt if n_gt > 0 else 1.0
    precision = len(pred_used) / n_pred if n_pred > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Global score combinant cardinalité (40%) et alignement (60%)
    # L'alignement est ici représenté par la moyenne des IoU pondérée par le recall
    alignment_score = mean_iou * recall
    
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*50)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*50)
    print(f"- Cardinalité (40%) : {cardinality_score*100:.1f}% ({n_pred}/{n_gt} segments)")
    print(f"- Alignement & IoU (60%) : {alignment_score*100:.1f}%")
    print("-" * 20)
    print(f"- Precision : {precision*100:.1f}%")
    print(f"- Recall    : {recall*100:.1f}%")
    print(f"- F1-Score  : {f1*100:.1f}%")
    print(f"- IoU Moyen : {mean_iou*100:.1f}%")
    print("="*50)

    # Détails des segments si demandé
    if n_pred > 0:
        print("\nSegments prédits :")
        for i, p in enumerate(predictions):
            print(f"  {p['start']} -> {p['end']} (Conf: {p['confidence']})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évaluer la qualité des prédictions smooth.")
    parser.add_argument("--model_type", type=str, default="ast", choices=["ast", "wav2vec2", "beats", "wavlm", "cnn"], help="Type de modèle")
    parser.add_argument("--model_dir", type=str, help="Répertoire du modèle (optionnel)")
    parser.add_argument("--audio", type=str, required=True, help="Chemin vers le fichier audio")
    parser.add_argument("--gt", type=str, default="test_gt.txt", help="Chemin vers le fichier de vérité terrain")
    parser.add_argument("--threshold", type=float, default=0.5, help="Seuil de détection")
    parser.add_argument("--smooth_window", type=int, default=5, help="Fenêtre de lissage")
    parser.add_argument("--window", type=float, default=10.0, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=5.0, help="Overlap in seconds")
    
    args = parser.parse_args()
    
    evaluate_quality(
        model_type=args.model_type,
        model_dir=args.model_dir,
        audio_path=args.audio,
        tc_path=args.gt,
        threshold=args.threshold,
        smooth_window=args.smooth_window,
        window_size=args.window,
        overlap=args.overlap
    )
