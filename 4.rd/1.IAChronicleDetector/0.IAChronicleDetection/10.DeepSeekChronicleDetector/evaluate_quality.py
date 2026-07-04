import os
import argparse
import json
import sys
from pathlib import Path
from detector import ChronicleDetector

def evaluate_quality(transcription_file, gt_file, chroniques_prompt):
    detector = ChronicleDetector(chroniques_prompt)
    
    with open(transcription_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    sentences = [s.strip() for s in text.split('.') if s.strip()] # Simplifié
    
    print(f"--- Évaluation LIVE DeepSeek ---")

    # Chargement GT
    with open(gt_file, 'r') as f:
        # ... logic to load GT intervals
        gt_intervals = [] # Placeholder

    for det_res in detections:
        # Trouver match GT
        # ...
        # latency = det_time - gt_start
        # print(f"Chronique: {det_res['chronique']} | Latence: {latency}s")
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    args = parser.parse_args()
    
    # Prompt par défaut pour France Inter
    prompt = ["Le journal de 7h", "Le journal de 8h", "L'invité de 8h20"]
    evaluate_quality(args.audio, args.gt, prompt)
