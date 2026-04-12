import numpy as np
import torch
from train import RadioChroniqueClassifier, HybridSequenceClassifier
from utils import load_transcription, format_timecode, save_predictions
from typing import List, Tuple
import os

def predict_chroniques(base_model_path: str, hybrid_model_path: str, srt_file: str,
                       confidence_threshold: float = 0.5,
                       min_chronique_duration: float = 10.0,
                       max_gap_duration: float = 2.0,
                       smoothing_window: int = 5) -> List[Tuple[float, float]]:
    """Prédit les chroniques avec le modèle Hybride (CamemBERT + Bi-LSTM + CRF)"""

    print(f"Chargement des modèles hybrides...")
    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
    
    segments = load_transcription(srt_file)
    if not segments: return []
    
    # Extraction des features (BERT inclus)
    X = base_extractor.prepare_features(segments, training=False)
    
    # Prédiction séquentielle
    all_probs = hybrid_model.predict(X)
    
    # Probabilité d'être dans une chronique (classe 1=Début ou 2=Dedans)
    # Note: Dans la version CRF, on a souvent des probabilités binaires (0 ou 1)
    probs = all_probs[:, 1] + all_probs[:, 2]
    pred_classes = np.argmax(all_probs, axis=1)
    
    # Lissage (optionnel pour CRF mais utile pour les durées)
    if smoothing_window > 1:
        smoothed_probs = np.convolve(probs, np.ones(smoothing_window)/smoothing_window, mode='same')
    else:
        smoothed_probs = probs
        
    # Grouper les segments
    raw_chroniques = []
    current_start = None
    
    for i, prob in enumerate(smoothed_probs):
        is_chronique = prob >= confidence_threshold
        is_new_start = pred_classes[i] == 1
        
        if is_chronique:
            # Si on détecte un nouveau début alors qu'on était déjà dans une chronique
            if is_new_start and current_start is not None:
                raw_chroniques.append((current_start, segments[i-1]['end']))
                current_start = segments[i]['start']
            
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
    final_chroniques = [(s, e) for s, e in merged_chroniques if (e - s) >= min_chronique_duration]
    
    return final_chroniques

if __name__ == "__main__":
    base_model = "models/radio_chronique_hybrid_base.pkl"
    hybrid_model = "models/radio_chronique_hybrid_hybrid.pt"
    srt_file = "../../@assets/transcriptions/10241-26.03.2026-ITEMA_24454073-2026F10761S0085-NET_MFI_901E1674-BE5E-4736-8973-E89E8FDD16FC-22-0516b94cb96f2aff4a338087e57e07af.srt"
    
    if not (os.path.exists(base_model) and os.path.exists(hybrid_model)):
        print("Modèles non trouvés. Veuillez d'abord lancer train.py.")
    else:
        chroniques = predict_chroniques(base_model, hybrid_model, srt_file)
        print(f"\nChroniques détectées: {len(chroniques)}")
        for i, (start, end) in enumerate(chroniques, 1):
            print(f"{i}: {format_timecode(start)} - {format_timecode(end)}")
        save_predictions(chroniques, "predictions_output.txt")
