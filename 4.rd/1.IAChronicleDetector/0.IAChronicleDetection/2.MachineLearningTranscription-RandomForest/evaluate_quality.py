import os
import argparse
import json
import sys
import numpy as np
from pathlib import Path

# Ajout du dossier courant au path pour les imports locaux
sys.path.append(os.getcwd())
from predict import predict_chroniques
from utils import load_timecodes

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def evaluate_quality(model_path, srt_path, tc_path):
    if not os.path.exists(model_path):
        print(f"Erreur : Le modèle '{model_path}' n'existe pas.")
        return
    if not os.path.exists(srt_path):
        print(f"Erreur : La transcription '{srt_path}' n'existe pas.")
        return
    if not os.path.exists(tc_path):
        print(f"Erreur : Les timecodes '{tc_path}' n'existent pas.")
        return

    print(f"--- Évaluation de Qualité (40/60) pour Random Forest ---")
    
    # 1. Prédire
    print(f"Analyse de {srt_path}...")
    # On utilise la fonction de prédiction existante du projet
    final_chroniques, _ = predict_chroniques(model_path, srt_path, gt_file=None)
    pred_intervals = final_chroniques

    print(f"\n📺 Chroniques détectées par le modèle :")
    print("-" * 60)
    print(f"{'Index':<5} | {'Début (s)':<10} | {'Fin (s)':<10}")
    print("-" * 60)
    for i, (start, end) in enumerate(pred_intervals, 1):
        print(f"{i:<5} | {start:<10.1f} | {end:<10.1f}")
    print("-" * 60)

    # 2. Charger la vérité terrain
    gt_intervals = load_timecodes(tc_path)
    print(f"\n✅ Vérité Terrain (Ground Truth) chargée : {len(gt_intervals)} chroniques attendues.")
    
    # 3. Calculer les métriques et afficher la comparaison
    print(f"\n🔍 Comparaison détaillée :")
    print("-" * 80)
    print(f"{'GT Index':<10} | {'GT Intervalle':<20} | {'Match Pred':<15} | {'IoU':<6} | {'Status'}")
    print("-" * 80)

    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    
    chronicle_scores = []
    pred_used = set()
    max_offset_tolerance = 60.0

    for i, gt in enumerate(gt_intervals, 1):
        best_iou = 0
        best_p_idx = -1
        for p_idx, p in enumerate(pred_intervals):
            if p_idx in pred_used: continue
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_p_idx = p_idx
        
        gt_str = f"{gt[0]:.1f}s - {gt[1]:.1f}s"
        if best_p_idx != -1 and best_iou > 0:
            pred_used.add(best_p_idx)
            p = pred_intervals[best_p_idx]
            offset = (abs(p[0] - gt[0]) + abs(p[1] - gt[1])) / 2
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
            
            p_str = f"{p[0]:.1f}s - {p[1]:.1f}s"
            print(f"{i:<10} | {gt_str:<20} | {p_str:<15} | {best_iou:<6.2f} | ✅ OK")
        else:
            chronicle_scores.append(0.0)
            print(f"{i:<10} | {gt_str:<20} | {'-'*15:<15} | {0.0:<6.2f} | ❌ MISS")

    # Signaler les prédictions en trop (Faux Positifs)
    for p_idx, p in enumerate(pred_intervals):
        if p_idx not in pred_used:
            p_str = f"{p[0]:.1f}s - {p[1]:.1f}s"
            print(f"{'EXTRA':<10} | {'-'*20:<20} | {p_str:<15} | {'-':<6} | ⚠️ FP")

    print("-" * 80)

    # Calcul des scores finaux (Standardisés)
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*40)
    print(f"- Modèle : {model_path}")
    print(f"- Chroniques : {n_pred} détectées / {n_gt} attendues")
    print(f"- La Cardinalité (40%) : {cardinality_score*100:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {alignment_score*100:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue la qualité de détection pour le modèle Random Forest.")
    parser.add_argument("--model", default="models/radio_chronique_rf.pkl", help="Chemin vers le modèle (.pkl)")
    parser.add_argument("--srt", required=True, help="Chemin vers la transcription SRT")
    parser.add_argument("--gt", required=True, help="Chemin vers le ground truth (timecodes)")
    
    args = parser.parse_args()
    evaluate_quality(args.model, args.srt, args.gt)
