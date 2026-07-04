import argparse
import json
import sys
import os
from pathlib import Path
from detect import FilePipeline

def evaluate_quality(audio_path, gt_path, config_path="config/default.yaml"):
    if not os.path.exists(audio_path):
        print(f"Erreur: Audio non trouvé {audio_path}")
        return
        
    print(f"--- Évaluation Pipeline Multi-Approche pour {audio_path} ---")
    
    pipeline = FilePipeline(config_path, audio_path)
    detections = pipeline.run_on_file()
    
    print(f"\n📊 Résultats : {len(detections)} chroniques détectées.")
    
    # Chargement GT
    gt_intervals = []
    if os.path.exists(gt_path):
        with open(gt_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2: gt_intervals.append((float(parts[0]), float(parts[1])))

    for det in detections:
        best_gt = None
        min_diff = float('inf')
        for gt in gt_intervals:
            diff = abs(det['start'] - gt[0])
            if diff < min_diff:
                min_diff = diff
                best_gt = gt
        
        if best_gt and min_diff < 60:
            latency = det['start'] - best_gt[0]
            print(f"Détection ({det.get('method')}) à {det['start']}s -> Latence: {latency:.1f}s")
        else:
            print(f"Détection à {det['start']}s -> FP?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--config", default="config/default.yaml")
    args = parser.parse_args()
    evaluate_quality(args.audio, args.gt, args.config)
