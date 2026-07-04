import os
import argparse
import json
import sys
import ollama
from pathlib import Path
import re

MODEL = "mistral"

def evaluate_quality_live(srt_path, gt_path):
    print(f"--- Évaluation LIVE (LLM Global) ---")
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # En live sim, on pourrait envoyer des morceaux de transcription
    # Mais l'approche 0 est "Global", donc elle attend tout.
    # Pour simuler le live, on va envoyer la transcription accumulée toutes les 5 minutes.
    
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    for line in lines:
        current_chunk.append(line)
        if "-->" in line:
            # Extraction du temps pour chunker toutes les 300s
            m = re.search(r'(\d{2}):(\d{2}):(\d{2})', line)
            if m:
                s = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
                if s > 0 and s % 300 == 0:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    all_detections = []
    for i, chunk in enumerate(chunks):
        print(f"Analyse chunk {i+1}/{len(chunks)}...")
        # Appel LLM (simulé ici pour l'exemple d'évaluation)
        # res = call_llm(chunk)
        # all_detections.extend(res)
        pass

    print("Fin de l'évaluation live.")
    
    # Chargement GT
    gt_intervals = []
    if os.path.exists(gt_path):
        with open(gt_path, 'r') as f:
            # parsing timecodes...
            pass

    for det in all_detections:
        # latency = det_start - gt_start
        # print(f"Latence: {latency}s")
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    args = parser.parse_args()
    evaluate_quality_live(args.audio, args.gt)
