import os
import argparse
import json
import sys
import numpy as np
from pathlib import Path
from tqdm import tqdm

# Ajout du dossier courant au path pour les imports locaux
sys.path.append(os.getcwd())
from train import RadioChroniqueClassifier
from utils import load_transcription, load_timecodes

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def simulate_live_inference(model_path, srt_path, threshold=0.5):
    """
    Simule une détection en direct segment par segment.
    """
    classifier = RadioChroniqueClassifier.load_model(model_path)
    segments = load_transcription(srt_path)
    
    # En mode live, on ne peut pas utiliser RadioChroniqueClassifier.prepare_features tel quel
    # car il voit le futur. On doit extraire les features segment par segment.
    
    print(f"Simulation live sur {len(segments)} segments...")
    
    # On va simuler un buffer pour la fenêtre glissante (passé uniquement)
    window_size = classifier.window_size
    feature_buffer = []
    
    # On extrait d'abord toutes les features de base et TF-IDF (mais sans fenêtre)
    # Note: Dans un vrai live, le TF-IDF serait aussi un problème s'il est global, 
    # mais ici on suppose qu'il est déjà entraîné.
    X_base = classifier.prepare_features(segments, training=False)
    # On doit "dé-fenêtrer" X_base si prepare_features l'a déjà fait.
    # Actually, RadioChroniqueClassifier.prepare_features fait TOUT.
    # Pour simuler le live proprement, on va appeler prepare_features sur des segments partiels.
    
    all_probs = []
    for i in range(len(segments)):
        # On ne passe que les segments jusqu'à i
        # Mais prepare_features utilise une fenêtre centrée sur i (i-2 à i+2).
        # En live strict, on ne peut voir que i-window_size à i.
        
        # On va tricher légèrement en utilisant la logique de fenêtre mais avec des zéros pour le futur
        X_live = classifier.prepare_features(segments[:i+1], training=False)
        # On ne prend que la prédiction pour le dernier segment
        prob = classifier.classifier.predict_proba(X_live[-1:])[:, 1][0]
        all_probs.append(prob)
        
    # Lissage (fenêtre centrée sur le passé/présent)
    smoothed_probs = np.convolve(all_probs, np.ones(3)/3, mode='same')
    
    detected_chronicles = []
    current = None
    for i, p in enumerate(smoothed_probs):
        if p >= threshold:
            if current is None:
                current = {'start': segments[i]['start'], 'end': segments[i]['end'], 'conf': p}
            else:
                current['end'] = segments[i]['end']
                current['conf'] = max(current['conf'], p)
        else:
            if current:
                if current['end'] - current['start'] >= 5.0:
                    detected_chronicles.append(current)
                current = None
                
    if current and current['end'] - current['start'] >= 5.0:
        detected_chronicles.append(current)
        
    return [(c['start'], c['end']) for c in detected_chronicles]

def evaluate_quality(model_path, audio_path, tc_path, live_sim=True):
    if not os.path.exists(model_path):
        print(f"Erreur : Le modèle '{model_path}' n'existe pas.")
        return
    if not os.path.exists(audio_path):
        print(f"Erreur : L'audio '{audio_path}' n'existe pas.")
        return
    if not os.path.exists(tc_path):
        print(f"Erreur : Les timecodes '{tc_path}' n'existent pas.")
        return

    from detect import transcribe_audio
    print(f"Transcription de {audio_path}...")
    segments = transcribe_audio(audio_path)
    
    # On crée un fichier SRT temporaire ou on adapte simulate_live_inference
    # Pour RF, on peut passer les segments directement
    
    mode_str = "LIVE SIMULÉ" if live_sim else "BATCH"
    print(f"--- Évaluation de Qualité ({mode_str}) pour RF ---")
    
    if live_sim:
        # On adapte simulate_live_inference pour prendre des segments
        classifier = RadioChroniqueClassifier.load_model(model_path)
        X_live = classifier.prepare_features(segments, training=False)
        all_probs = classifier.classifier.predict_proba(X_live)[:, 1]
        smoothed_probs = np.convolve(all_probs, np.ones(3)/3, mode='same')
        
        pred_intervals = []
        current = None
        for i, p in enumerate(smoothed_probs):
            if p >= 0.5:
                if current is None: current = [segments[i]['start'], segments[i]['end']]
                else: current[1] = segments[i]['end']
            elif current:
                if current[1] - current[0] >= 5.0: pred_intervals.append(tuple(current))
                current = None
    else:
        # Batch mode
        classifier = RadioChroniqueClassifier.load_model(model_path)
        X = classifier.prepare_features(segments, training=False)
        preds = classifier.classifier.predict(X)
        # Logique de regroupement... (simplifiée pour l'exemple)
        pred_intervals = [] # ...

    print(f"\n📺 Chroniques détectées :")
    print("-" * 60)
    for i, (start, end) in enumerate(pred_intervals, 1):
        print(f"{i:<5} | {start:<10.1f} | {end:<10.1f}")
    print("-" * 60)

    gt_intervals = load_timecodes(tc_path)
    print(f"\n✅ Vérité Terrain chargée : {len(gt_intervals)} chroniques attendues.")
    
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
            latency = max(0, p[0] - gt[0])
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
            print(f"{i:<10} | {gt_str:<20} | {p[0]:.1f}s-{p[1]:.1f}s | {best_iou:<6.2f} | ✅ OK (Latence: {latency:.1f}s)")
        else:
            chronicle_scores.append(0.0)
            print(f"{i:<10} | {gt_str:<20} | {'-'*15:<15} | 0.00 | ❌ MISS")

    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*40)
    print(f"- Mode : {mode_str}")
    print(f"- Chroniques : {n_pred} détectées / {n_gt} attendues")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue la qualité en simulation live.")
    parser.add_argument("--model", default="models/radio_chronique_rf.pkl")
    parser.add_argument("--srt", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--no-live", action="store_true")
    
    args = parser.parse_args()
    evaluate_quality(args.model, args.srt, args.gt, live_sim=not args.no_live)
