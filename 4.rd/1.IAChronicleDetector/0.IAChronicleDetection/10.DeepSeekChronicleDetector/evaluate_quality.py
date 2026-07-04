import os
import argparse
import json
import sys
import time
from pathlib import Path
from detector import ChronicleDetector
from transcriber import Transcriber

def evaluate_quality(audio_path, gt_file, acceleration=1.0, model_size="base"):
    if not os.path.exists(audio_path):
        print(f"Erreur : Audio non trouvé {audio_path}")
        return

    # Chargement GT
    gt_intervals = []
    if os.path.exists(gt_file):
        with open(gt_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    gt_intervals.append((float(parts[0]), float(parts[1])))
    else:
        print(f"Attention : Fichier GT non trouvé {gt_file}")

    # Prompt par défaut pour France Inter
    prompt = ["Le journal de 7h", "Le journal de 8h", "L'invité de 8h20"]
    detector = ChronicleDetector(prompt)
    transcriber = Transcriber(model_size=model_size)
    
    print(f"--- Évaluation LIVE DeepSeek (Accélération: {acceleration}x) ---")
    
    detections = []
    start_wall_time = time.time()

    # On utilise transcribe_stream pour simuler le flux
    for segment in transcriber.transcribe_stream(audio_path):
        text = segment["text"]
        if not text:
            continue
            
        # Simulation du délai live
        if acceleration > 0:
            target_wall_time = segment["start"] / acceleration
            elapsed = time.time() - start_wall_time
            if target_wall_time > elapsed:
                time.sleep(target_wall_time - elapsed)

        print(f"[{segment['start']:.1f}s] Analyse : {text[:50]}...")
        result = detector.analyze_sentence(text)
        
        if result.get("detecte"):
            chronique_name = result.get("chronique")
            print(f"🔔 DÉTECTION : {chronique_name}")
            detections.append({
                "start": segment["start"],
                "chronique": chronique_name
            })

    print(f"\n📊 Résultats : {len(detections)} chroniques détectées.")
    
    # Comparaison avec GT
    for det in detections:
        best_gt = None
        min_diff = float('inf')
        for gt in gt_intervals:
            diff = abs(det['start'] - gt[0])
            if diff < min_diff:
                min_diff = diff
                best_gt = gt
        
        if best_gt and min_diff < 120:
            latency = det['start'] - best_gt[0]
            print(f"Chronique '{det['chronique']}' à {det['start']:.1f}s -> OK (Latence: {latency:.1f}s)")
        else:
            print(f"Chronique '{det['chronique']}' à {det['start']:.1f}s -> FP?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--acceleration", type=float, default=1.0)
    parser.add_argument("--model", default="base")
    args = parser.parse_args()
    
    evaluate_quality(args.audio, args.gt, acceleration=args.acceleration, model_size=args.model)
