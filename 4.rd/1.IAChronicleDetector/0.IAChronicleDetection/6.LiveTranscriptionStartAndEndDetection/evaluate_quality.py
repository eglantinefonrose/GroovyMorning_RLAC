import os
import argparse
import json
import sys
import numpy as np
from pathlib import Path
from inference_live_sim import LiveChronicleDetector
from inference import clean_srt_content
import re

def evaluate_quality_live(model_path, audio_path, gt_path, threshold=0.8):
    from detect import transcribe_audio
    print(f"Transcription de {audio_path}...")
    segments = transcribe_audio(audio_path)
    
    detector = LiveChronicleDetector(model_path=model_path, threshold=threshold)
    detections = []
    for seg in segments:
        res = detector.process_new_sentence(seg['text'])
        if res:
            res['start'] = seg['start']
            detections.append(res)
            
    print(f"--- Évaluation LIVE pour {model_path} ---")
    
    # Chargement GT pour calcul latence
    from inference import load_timecodes
    gt_intervals = load_timecodes(gt_path)
    
    for det in detections:
        # Trouver la chronique GT la plus proche
        best_gt = None
        min_diff = float('inf')
        for gt in gt_intervals:
            diff = abs(det['start'] - gt[0])
            if diff < min_diff:
                min_diff = diff
                best_gt = gt
        
        if best_gt and min_diff < 120: # Match si à moins de 2 mins
            latency = det['start'] - best_gt[0]
            print(f"Détection à {det['start']:.1f}s (GT: {best_gt[0]:.1f}s) -> Latence: {latency:.1f}s")
        else:
            print(f"Détection à {det['start']:.1f}s -> Faux Positif ?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="./camembert_chronicle_start_v4")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    args = parser.parse_args()
    evaluate_quality_live(args.model, args.audio, args.gt)
