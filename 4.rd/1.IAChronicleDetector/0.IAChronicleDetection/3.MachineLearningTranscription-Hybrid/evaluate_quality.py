import os
import argparse
import json
import sys
import time
import numpy as np
import torch
from pathlib import Path
from tqdm import tqdm

# Ajout du dossier courant au path pour les imports locaux
sys.path.append(os.getcwd())
from train import RadioChroniqueClassifier, HybridSequenceClassifier
from utils import load_transcription, load_timecodes

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def simulate_live_inference(base_model_path, hybrid_model_path, srt_path, acceleration=None):
    """
    Simule une détection en direct hybride.
    """
    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
    hybrid_model.device = torch.device('cpu')
    hybrid_model.model.to(torch.device('cpu'))
    
    segments = load_transcription(srt_path)
    print(f"Simulation live sur {len(segments)} segments...")
    if acceleration:
        print(f"Accélération : {acceleration}x")
        start_wall_time = time.time()
    
    seq_len = hybrid_model.seq_len
    all_preds = np.zeros(len(segments), dtype=int)
    all_probs = np.zeros(len(segments))
    
    # Simulation du flux : à chaque segment i, on regarde la fenêtre [i-seq_len+1, i]
    hybrid_model.model.eval()
    with torch.no_grad():
        for i in range(len(segments)):
            if acceleration and acceleration > 0:
                T = segments[i]['start']
                target_wall_time = T / acceleration
                elapsed = time.time() - start_wall_time
                if target_wall_time > elapsed:
                    time.sleep(target_wall_time - elapsed)

            # Fenêtre glissante finissant à i
            start_idx = max(0, i - seq_len + 1)
            end_idx = i + 1
            window_segments = segments[start_idx:end_idx]
            
            # Préparation des features pour cette fenêtre uniquement
            X_window = base_extractor.prepare_features(window_segments, training=False)
            
            # Padding si nécessaire pour atteindre seq_len
            if len(X_window) < seq_len:
                padding = np.zeros((seq_len - len(X_window), X_window.shape[1]))
                X_window = np.vstack([padding, X_window])
                
            X_tensor = torch.FloatTensor(X_window).unsqueeze(0).to(hybrid_model.device)
            
            # Décodage CRF
            preds = hybrid_model.model.decode(X_tensor)[0]
            # Probabilités
            emissions = hybrid_model.model.emissions(X_tensor)
            probs = torch.softmax(emissions, dim=2)[0, :, 1].cpu().numpy()
            
            # On ne garde que la décision pour l'élément actuel (le dernier de la fenêtre)
            all_preds[i] = preds[-1]
            all_probs[i] = probs[-1]

    detected_chronicles = []
    current = None
    for i, label in enumerate(all_preds):
        if label > 0:
            if current is None:
                current = {'start': segments[i]['start'], 'end': segments[i]['end'], 'conf': all_probs[i]}
            else:
                current['end'] = segments[i]['end']
                current['conf'] = max(current['conf'], all_probs[i])
        else:
            if current:
                if current['end'] - current['start'] >= 5.0:
                    detected_chronicles.append(current)
                current = None
                
    if current and current['end'] - current['start'] >= 5.0:
        detected_chronicles.append(current)
        
    return [(c['start'], c['end']) for c in detected_chronicles]

def evaluate_quality(base_model, hybrid_model, srt_path, tc_path, live_sim=True, acceleration=None):
    if not os.path.exists(base_model) or not os.path.exists(hybrid_model):
        print(f"Erreur : Modèles introuvables.")
        return
    if not os.path.exists(srt_path) or not os.path.exists(tc_path):
        print(f"Erreur : Fichiers SRT ou GT introuvables.")
        return

    mode_str = "LIVE SIMULÉ" if live_sim else "BATCH"
    print(f"--- Évaluation de Qualité ({mode_str}) pour Hybride ---")
    
    if live_sim:
        pred_intervals = simulate_live_inference(base_model, hybrid_model, srt_path, acceleration=acceleration)
    else:
        from predict import predict_chroniques
        pred_intervals, _ = predict_chroniques(base_model, hybrid_model, srt_path)

    print(f"\n📺 Chroniques détectées : {len(pred_intervals)}")
    
    gt_intervals = load_timecodes(tc_path)
    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    chronicle_scores = []
    pred_used = set()
    max_offset_tolerance = 60.0

    print(f"\n🔍 Comparaison détaillée :")
    for i, gt in enumerate(gt_intervals, 1):
        best_iou = 0
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
            latency = max(0, p[0] - gt[0])
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
            print(f"GT {i}: {gt[0]:.1f}s -> OK (Latence: {latency:.1f}s, IoU: {best_iou:.2f})")
        else:
            chronicle_scores.append(0.0)
            print(f"GT {i}: {gt[0]:.1f}s -> MISS")

    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*40)

def simulate_live_inference_on_segments(base_model_path, hybrid_model_path, segments):
    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
    hybrid_model.device = torch.device('cpu')
    hybrid_model.model.to(torch.device('cpu'))
    
    seq_len = hybrid_model.seq_len
    all_preds = np.zeros(len(segments), dtype=int)
    
    with torch.no_grad():
        for i in range(len(segments)):
            start_idx = max(0, i - seq_len + 1)
            window_segments = segments[start_idx:i+1]
            X_window = base_extractor.prepare_features(window_segments, training=False)
            if len(X_window) < seq_len:
                padding = np.zeros((seq_len - len(X_window), X_window.shape[1]))
                X_window = np.vstack([padding, X_window])
            X_tensor = torch.FloatTensor(X_window).unsqueeze(0)
            preds = hybrid_model.model.decode(X_tensor)[0]
            all_preds[i] = preds[-1]

    # Regroupement
    intervals = []
    curr = None
    for i, label in enumerate(all_preds):
        if label > 0:
            if curr is None: curr = [segments[i]['start'], segments[i]['end']]
            else: curr[1] = segments[i]['end']
        elif curr:
            if curr[1] - curr[0] >= 5.0: intervals.append(tuple(curr))
            curr = None
    return intervals

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue la qualité en simulation live.")
    parser.add_argument("--base", default="models/radio_chronique_hybrid_base.pkl")
    parser.add_argument("--hybrid", default="models/radio_chronique_hybrid_hybrid.pt")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--acceleration", type=float, default=None, help="Acceleration factor for live simulation")
    
    args = parser.parse_args()
    evaluate_quality(args.base, args.hybrid, args.audio, args.gt, live_sim=not args.no_live, acceleration=args.acceleration)
