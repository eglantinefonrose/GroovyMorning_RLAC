import numpy as np
import joblib
import time
from train import RadioChroniqueClassifier
from utils import load_transcription, format_timecode, save_predictions, calculate_quality_score, load_timecodes
from typing import List, Tuple
import os

def predict_chroniques(model_path: str, srt_file: str,
                       confidence_threshold: float = 0.4, # Seuil légèrement abaissé pour debug
                       min_chronique_duration: float = 5.0, # Durée abaissée pour debug
                       max_gap_duration: float = 2.0,
                       smoothing_window: int = 3,
                       gt_file: str = None) -> Tuple[List[Tuple[float, float]], dict]:
    """Prédit les chroniques avec Random Forest"""

    start_time = time.time()
    print(f"--- Diagnostic de prédiction ---")
    print(f"Modèle: {model_path}")
    print(f"Fichier SRT: {srt_file}")
    
    classifier = RadioChroniqueClassifier.load_model(model_path)
    
    segments = load_transcription(srt_file)
    if not segments:
        print("Erreur: Aucun segment chargé depuis le SRT.")
        return [], {}
    print(f"Segments chargés: {len(segments)}")
    
    X = classifier.prepare_features(segments, training=False)
    
    # Gestion du cas où le modèle n'a qu'une seule classe (ex: que des zéros pendant l'entraînement)
    if len(classifier.classifier.classes_) == 1:
        print(f"Attention: Le modèle n'a été entraîné que sur une seule classe ({classifier.classifier.classes_[0]}).")
        if classifier.classifier.classes_[0] == 1:
            probs = np.ones(len(X))
        else:
            probs = np.zeros(len(X))
    else:
        probs = classifier.classifier.predict_proba(X)[:, 1]
    
    print(f"Probabilité max détectée: {np.max(probs):.4f}")
    
    # Lissage des probabilités
    if smoothing_window > 1:
        smoothed_probs = np.convolve(probs, np.ones(smoothing_window)/smoothing_window, mode='same')
    else:
        smoothed_probs = probs
        
    # Grouper les segments
    raw_chroniques = []
    current_start = None
    
    for i, prob in enumerate(smoothed_probs):
        is_chronique = prob >= confidence_threshold
        
        if is_chronique:
            if current_start is None:
                current_start = segments[i]['start']
            else:
                if i > 0 and (segments[i]['start'] - segments[i-1]['end']) > max_gap_duration:
                    raw_chroniques.append((current_start, segments[i-1]['end']))
                    current_start = segments[i]['start']
        else:
            if current_start is not None:
                raw_chroniques.append((current_start, segments[i-1]['end']))
                current_start = None
                
    if current_start is not None:
        raw_chroniques.append((current_start, segments[-1]['end']))
    
    # Fusionner les blocs très proches
    merged_chroniques = []
    if raw_chroniques:
        curr_start, curr_end = raw_chroniques[0]
        for i in range(1, len(raw_chroniques)):
            next_start, next_end = raw_chroniques[i]
            if next_start - curr_end <= max_gap_duration:
                curr_end = next_end
            else:
                merged_chroniques.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged_chroniques.append((curr_start, curr_end))
    
    # Filtrer par durée
    final_chroniques = [
        (s, e) for s, e in merged_chroniques 
        if (e - s) >= min_chronique_duration
    ]
    
    processing_time = time.time() - start_time
    audio_duration = segments[-1]['end'] if segments else 3600
    
    quality_report = {}
    if gt_file and os.path.exists(gt_file):
        ground_truth = load_timecodes(gt_file)
        quality_report = calculate_quality_score(final_chroniques, ground_truth, processing_time, audio_duration)
        
    return final_chroniques, quality_report

if __name__ == "__main__":
    # Configuration
    model_path = "models/radio_chronique_rf.pkl"
    srt_file = "../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_transcription.srt"
    gt_file = "../../@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_timecode_chronique.txt"

    if not os.path.exists(model_path):
        print(f"Modèle non trouvé: {model_path}. Veuillez d'abord lancer train.py.")
    elif not os.path.exists(srt_file):
        print(f"Fichier SRT non trouvé: {srt_file}")
    else:
        chroniques, quality = predict_chroniques(model_path, srt_file, gt_file=gt_file)
        print(f"\n=== RESULTAT FINAL ===")
        print(f"Chroniques validées: {len(chroniques)}")
        for i, (start, end) in enumerate(chroniques, 1):
            print(f"{i}: {format_timecode(start)} - {format_timecode(end)}")
        
        if quality:
            print(f"\n=== NOTE DE QUALITÉ : {quality['total_score']}/100 ===")
            print(f"Détails :")
            for k, v in quality['details'].items():
                print(f"  - {k}: {v}")
                
        save_predictions(chroniques, "predictions_output.txt")
