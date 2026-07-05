import argparse
import json
import sys
import os
from pathlib import Path
from detect import transcribe_audio, analyze_segment_with_llm

import time

def evaluate_quality(audio_path, gt_path, acceleration=1.0):
    if not os.path.exists(audio_path):
        print(f"Erreur: Audio non trouvé {audio_path}")
        return
        
    print(f"--- Évaluation LIVE (LLM Qwen) pour {audio_path} ---")
    segments = transcribe_audio(audio_path)
    
    history = []
    detections = []
    
    t0 = time.time()
    print(f"Traitement de {len(segments)} segments...", file=sys.stderr)
    for seg in segments:
        if acceleration > 0:
            target_time = seg['start'] / acceleration
            elapsed = time.time() - t0
            sleep_time = target_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        res_raw = analyze_segment_with_llm(seg['text'], history)
        try:
            res = json.loads(res_raw)
            if res.get("detecte"):
                detections.append({
                    "start": round(seg['start'], 2),
                    "end": round(seg['start'] + 60.0, 2), # Durée par défaut
                    "label": res.get("chronique", "chronique"),
                    "confidence": 1.0
                })
            history.append({"role": "user", "content": seg['text']})
            history.append({"role": "assistant", "content": res_raw})
        except:
            pass
            
    print(f"\n📊 Résultats : {len(detections)} chroniques détectées.")
    
    # Chargement GT (simplifié pour l'exemple)
    from main import split_sentences # ou autre utilitaire
    # On suppose que gt_path est un fichier de timecodes
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
        
        if best_gt and min_diff < 120:
            latency = det['start'] - best_gt[0]
            print(f"Chronique '{det['label']}' détectée à {det['start']}s -> Latence: {latency:.1f}s")
        else:
            print(f"Chronique '{det['label']}' détectée à {det['start']}s -> FP?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--acceleration", type=float, default=1.0)
    args = parser.parse_args()
    evaluate_quality(args.audio, args.gt, acceleration=args.acceleration)
