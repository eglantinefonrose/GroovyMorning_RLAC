import os
import argparse
import json
import sys
import numpy as np
from pathlib import Path

# Ajout du dossier src au path pour les imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from predict import predict

def hms_to_seconds(hms):
    parts = hms.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(hms)

def evaluate_quality(model_type, audio_path, tc_path, threshold=0.4, live_sim=True):
    # En réalité, predict fait déjà du sliding window, 
    # donc "live_sim" consiste ici à appeler predict avec les bons paramètres.
    
    print(f"--- Évaluation de Qualité ({'LIVE' if live_sim else 'BATCH'}) pour {model_type} ---")
    
    results = predict(
        audio_path=audio_path,
        model_type=model_type,
        threshold=threshold,
        window_size=10.0 if live_sim else 30.0,
        overlap=5.0 if live_sim else 0.0
    )
    
    pred_intervals = []
    for res in results:
        pred_intervals.append((hms_to_seconds(res['start']), hms_to_seconds(res['end'])))
    
    # Chargement GT
    with open(tc_path, 'r') as f:
        gt_data = [line.strip().split(',') for line in f if line.strip()]
        gt_intervals = [(float(x[0]), float(x[1])) for x in gt_data]

    # Calcul simplifié
    print(f"Détectées: {len(pred_intervals)} / Attendues: {len(gt_intervals)}")
    
    pred_used = set()
    for i, gt in enumerate(gt_intervals, 1):
        best_iou = 0
        best_p = None
        for p in pred_intervals:
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_p = p
        
        if best_p:
            latency = max(0, best_p[0] - gt[0])
            print(f"GT {i} ({gt[0]:.1f}s): OK (Latence: {latency:.1f}s)")
        else:
            print(f"GT {i} ({gt[0]:.1f}s): MISS")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ast")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    args = parser.parse_args()
    evaluate_quality(args.model, args.audio, args.gt)
