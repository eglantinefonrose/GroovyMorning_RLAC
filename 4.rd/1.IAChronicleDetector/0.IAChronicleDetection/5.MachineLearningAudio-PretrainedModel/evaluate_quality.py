import os
import argparse
import json
import sys
import glob
import numpy as np

# Ajout du dossier src au path pour les imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from predict import predict

def find_file_robustly(original_path):
    if os.path.exists(original_path): return original_path
    filename = os.path.basename(original_path)
    alt_filename = filename.replace("transcription_chronique", "timecode_chronique").replace("timecode_chronique", "transcription_chronique")
    for depth in ["./", "../", "../../", "../../../", "../../../../"]:
        assets_dir = os.path.join(depth, "@assets")
        if os.path.exists(assets_dir):
            for fname in [filename, alt_filename]:
                matches = glob.glob(os.path.join(assets_dir, "**", fname), recursive=True)
                if matches: return matches[0]
    return original_path

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def parse_time(time_str):
    h, m, s = time_str.split(':')
    s, ms = s.split('.')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def evaluate_quality(model_dir, audio_path, tc_path, model_type="wav2vec2"):
    if not os.path.exists(model_dir):
        print(f"Erreur : Le modèle '{model_dir}' n'existe pas.")
        return

    audio_path = find_file_robustly(audio_path)
    tc_path = find_file_robustly(tc_path)

    print(f"--- Évaluation de Qualité (40/60) pour {model_dir} ---")
    
    # 1. Prédire
    predictions = predict(audio_path, model_type=model_type, model_dir=model_dir)
    pred_intervals = [(parse_time(p['start']), parse_time(p['end'])) for p in predictions]

    # 2. Charger la vérité terrain
    with open(tc_path, 'r', encoding='utf-8') as f:
        gt_data = [line.strip().split('|') for line in f if '|' in line]
    gt_intervals = [(float(start), float(end)) for start, end in gt_data]
    
    # 3. Calculer les métriques
    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    
    chronicle_scores = []
    pred_used = set()
    max_offset_tolerance = 60.0

    for gt in gt_intervals:
        best_iou = -1
        best_p_idx = -1
        for p_idx, p in enumerate(pred_intervals):
            if p_idx in pred_used: continue
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_p_idx = p_idx
        
        if best_p_idx != -1 and best_iou > 0:
            pred_used.add(best_p_idx)
            p = pred_intervals[best_p_idx]
            offset = (abs(p[0] - gt[0]) + abs(p[1] - gt[1])) / 2
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
        else:
            chronicle_scores.append(0.0)

    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*40)
    print(f"- La Cardinalité (40%) : {cardinality_score*100:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {alignment_score*100:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir")
    parser.add_argument("audio_path")
    parser.add_argument("tc_path")
    parser.add_argument("--type", default="wav2vec2")
    args = parser.parse_args()
    evaluate_quality(args.model_dir, args.audio_path, args.tc_path, args.type)
