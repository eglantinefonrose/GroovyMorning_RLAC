import os
import argparse
import torch
import pandas as pd
import glob
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from src.utils import load_transcription, load_timecodes
from src.evaluation import evaluate_chronicles

def find_file_robustly(original_path):
    """Cherche le fichier récursivement dans @assets avec tolérance."""
    if os.path.exists(original_path):
        return original_path
    filename = os.path.basename(original_path)
    alt_filename = filename.replace("transcription_chronique", "timecode_chronique").replace("timecode_chronique", "transcription_chronique")
    for depth in ["./", "../", "../../", "../../../", "../../../../"]:
        assets_dir = os.path.join(depth, "@assets")
        if os.path.exists(assets_dir):
            for fname in [filename, alt_filename]:
                matches = glob.glob(os.path.join(assets_dir, "**", fname), recursive=True)
                if matches: return matches[0]
    return original_path

def evaluate_quality(model_path, srt_path, tc_path):
    if not os.path.exists(model_path):
        print(f"Erreur : Le modèle '{model_path}' n'existe pas.")
        return

    srt_path = find_file_robustly(srt_path)
    tc_path = find_file_robustly(tc_path)

    print(f"--- Évaluation de Qualité (40/60) pour {model_path} ---")
    
    # 1. Prédire (Réimplémentation légère pour flexibilité)
    import predict as pred_mod
    original_path = pred_mod.MODEL_PATH
    pred_mod.MODEL_PATH = model_path
    try:
        predicted_chronicles = pred_mod.predict(srt_path)
    finally:
        pred_mod.MODEL_PATH = original_path

    if predicted_chronicles is None: predicted_chronicles = []

    print(f"\n📺 Chroniques détectées par le modèle :")
    print("-" * 60)
    print(f"{'Index':<5} | {'Début (s)':<10} | {'Fin (s)':<10}")
    print("-" * 60)
    for i, p in enumerate(predicted_chronicles, 1):
        print(f"{i:<5} | {p['start']:<10.1f} | {p['end']:<10.1f}")
    print("-" * 60)

    # 2. Charger la vérité terrain
    ground_truth = load_timecodes(tc_path)
    print(f"\n✅ Vérité Terrain (Ground Truth) chargée : {len(ground_truth)} chroniques attendues.")
    
    # 3. Calculer les métriques
    metrics = evaluate_chronicles(predicted_chronicles, ground_truth)
    
    print(f"\n🔍 Comparaison détaillée :")
    print("-" * 80)
    print(f"{'GT Index':<10} | {'GT Intervalle':<20} | {'Match Pred':<15} | {'IoU':<6} | {'Status'}")
    print("-" * 80)

    pred_used = set()
    for detail in metrics['details']:
        gt_idx = detail['gt_idx']
        gt = ground_truth[gt_idx]
        gt_str = f"{gt[0]:.1f}s - {gt[1]:.1f}s"
        
        if detail['pred_idx'] is not None:
            p_idx = detail['pred_idx']
            pred_used.add(p_idx)
            p = predicted_chronicles[p_idx]
            p_str = f"{p['start']:.1f}s - {p['end']:.1f}s"
            print(f"{gt_idx+1:<10} | {gt_str:<20} | {p_str:<15} | {detail['iou']:<6.2f} | ✅ OK")
        else:
            print(f"{gt_idx+1:<10} | {gt_str:<20} | {'-'*15:<15} | {0.0:<6.2f} | ❌ MISS")

    # Signaler les prédictions en trop (Faux Positifs)
    for i, p in enumerate(predicted_chronicles):
        if i not in pred_used:
            p_str = f"{p['start']:.1f}s - {p['end']:.1f}s"
            print(f"{'EXTRA':<10} | {'-'*20:<20} | {p_str:<15} | {'-':<6} | ⚠️ FP")
    
    print("-" * 80)

    card_score = metrics['cardinality_score'] * 100
    align_score = metrics['alignment_score'] * 100
    global_score = (card_score * 0.4) + (align_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- La Cardinalité (40%) : {card_score:.1f}%")
    print(f"- L'Alignement Temporel (60%) : {align_score:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path")
    parser.add_argument("srt_path")
    parser.add_argument("tc_path")
    args = parser.parse_args()
    evaluate_quality(args.model_path, args.srt_path, args.tc_path)
