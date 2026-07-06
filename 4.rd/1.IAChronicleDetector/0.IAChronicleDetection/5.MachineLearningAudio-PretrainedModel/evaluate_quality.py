import os
import argparse
import json
import sys
import time
import numpy as np
import torch
import librosa
from pathlib import Path

# Ajout du dossier src au path pour les imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from predict import MODEL_CONFIGS, SAMPLING_RATE, format_time

def hms_to_seconds(hms):
    if isinstance(hms, (int, float)):
        return float(hms)
    parts = hms.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(hms)

def calculate_iou(interval_a, interval_b):
    """Calcule l'Intersection over Union entre deux intervalles (start, end)."""
    start_max = max(interval_a[0], interval_b[0])
    end_min = min(interval_a[1], interval_b[1])
    if end_min <= start_max:
        return 0.0
    intersection = end_min - start_max
    union = (interval_a[1] - interval_a[0]) + (interval_b[1] - interval_b[0]) - intersection
    return intersection / union

def evaluate_live_simulation(model_type, audio_path, tc_path=None, threshold=0.8, consecutive_needed=3, acceleration=1.0, output_path="resultat_live.json"):
    """
    Simule un flux audio live, effectue l'inférence fenêtre par fenêtre,
    et déclenche une alerte immédiate si N fenêtres consécutives dépassent le seuil.
    """
    print(f"\n" + "="*60)
    print(f"--- DÉMARRAGE DU MONITORING LIVE (SIMULÉ) ---")
    print(f"Modèle: {model_type.upper()}")
    print(f"Paramètres: Seuil={threshold}, Confirmation={consecutive_needed} fenêtres")
    print(f"Accélération: {acceleration}x")
    print("="*60 + "\n")
    
    # Chargement du Ground Truth (GT) si disponible
    gt_intervals = []
    if tc_path and os.path.exists(tc_path):
        with open(tc_path, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    gt_intervals.append((float(parts[0]), float(parts[1])))
    
    # Configuration et chargement du modèle
    config = MODEL_CONFIGS.get(model_type, MODEL_CONFIGS["ast"])
    model_dir = config["dir"]
    
    print(f"Chargement du modèle depuis {model_dir}...")
    model = config["model_class"].from_pretrained(model_dir)
    feature_extractor = config["extractor_class"].from_pretrained(model_dir)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device)
    model.eval()
    
    # Chargement de l'audio complet pour la simulation
    print(f"Chargement de l'audio {audio_path}...")
    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    
    window_size = 10.0
    overlap = 5.0
    step = window_size - overlap
    
    consecutive_hits = 0
    is_alerting = False
    detected_chronicles = []
    current_chronicle = None
    
    t_start_real = time.time()
    
    print(f"\n[DÉBUT DU FLUX - Durée totale: {format_time(duration)}]")
    print("-" * 40)

    # Boucle de simulation live
    for start in np.arange(0, duration - window_size, step):
        current_audio_time = start + window_size
        
        # Simulation du délai d'acquisition live
        if acceleration > 0:
            target_wall_time = current_audio_time / acceleration
            elapsed_wall_time = time.time() - t_start_real
            sleep_time = target_wall_time - elapsed_wall_time
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Temps "détecté à" (wall clock simulé)
        detected_at_time = current_audio_time
        
        # Extraction du segment (fenêtre)
        end = start + window_size
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        # Préparation des inputs
        if model_type == "ast":
            inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                     max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        else:
            inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", padding=True)
            
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Inférence
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            prob_chronique = probs[0][1].item()
            
        # Logique de décision LIVE
        if prob_chronique >= threshold:
            consecutive_hits += 1
            
            # Si on vient d'atteindre le nombre de fenêtres nécessaires
            if consecutive_hits == consecutive_needed and not is_alerting:
                is_alerting = True
                # Le début réel de la chronique est la première fenêtre de la série
                start_audio = round(start - (consecutive_needed - 1) * step, 2)
                
                current_chronicle = {
                    "label": "chronique",
                    "start": start_audio,
                    "end": round(end, 2),
                    "detected_at": round(detected_at_time, 2),
                    "confidence": round(prob_chronique, 3)
                }
                
                print(f"\n[{format_time(detected_at_time)}] 🚨 !!! ALERTE CHRONIQUE DÉTECTÉE !!! 🚨")
                print(f"      (Audio Start: {format_time(current_chronicle['start'])}, Confiance: {prob_chronique:.1%})")
                
                # Vérification GT si dispo
                if gt_intervals:
                    found_gt = False
                    for i, gt in enumerate(gt_intervals):
                        if gt[0] - 10 <= start_audio <= gt[1] + 10:
                            latency = detected_at_time - gt[0]
                            print(f"      ✅ VALIDATION: Correspond au GT #{i+1} (Début à {gt[0]:.1f}s)")
                            print(f"      ⏱️  LATENCE: {latency:.1f} secondes")
                            found_gt = True
                            break
                    if not found_gt:
                        print(f"      ❌ ALERTE FAUSSE: Aucun segment attendu à cet instant.")
                print("-" * 40)
            
            # Mise à jour de la confiance et de la fin si on est en alerte
            if is_alerting and current_chronicle:
                current_chronicle["confidence"] = max(current_chronicle["confidence"], round(prob_chronique, 3))
                current_chronicle["end"] = round(end, 2)

        else:
            if is_alerting and consecutive_hits == 0:
                print(f"  [{format_time(end)}] INFO: Fin de détection (Signal perdu)")
                if current_chronicle:
                    detected_chronicles.append(current_chronicle)
                    current_chronicle = None
                is_alerting = False
            consecutive_hits = 0

    # Fin de fichier : on enregistre si une chronique était en cours
    if is_alerting and current_chronicle:
        detected_chronicles.append(current_chronicle)

    # Sauvegarde JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(detected_chronicles, f, indent=4, ensure_ascii=False)
    
    print(f"\n" + "="*60)
    print(f"RÉSUMÉ DE LA SIMULATION")
    print(f"Alertes déclenchées: {len(detected_chronicles)}")
    print(f"Résultats sauvegardés dans: {output_path}")
    if gt_intervals:
        print(f"Segments attendus (GT): {len(gt_intervals)}")
    print("="*60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulation de détection de chroniques en live.")
    parser.add_argument("--model", default="ast", help="Type de modèle (ast, wav2vec2, etc.)")
    parser.add_argument("--audio", required=True, help="Chemin vers le fichier audio à simuler")
    parser.add_argument("--gt", help="Chemin vers le fichier de Ground Truth (optionnel)")
    parser.add_argument("--threshold", type=float, default=0.8, help="Seuil de probabilité")
    parser.add_argument("--consecutive", type=int, default=3, help="Nombre de fenêtres consécutives")
    parser.add_argument("--acceleration", type=float, default=1.0, help="Vitesse de simulation")
    parser.add_argument("--output", default="resultat_live.json", help="Fichier de sortie JSON")
    
    args = parser.parse_args()
    
    try:
        evaluate_live_simulation(
            model_type=args.model, 
            audio_path=args.audio, 
            tc_path=args.gt, 
            threshold=args.threshold, 
            consecutive_needed=args.consecutive,
            acceleration=args.acceleration,
            output_path=args.output
        )
    except KeyboardInterrupt:
        print("\n\nSimulation interrompue.")
        sys.exit(0)
