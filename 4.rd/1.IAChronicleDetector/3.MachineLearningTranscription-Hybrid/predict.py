import numpy as np
import torch
from train import RadioChroniqueClassifier, HybridSequenceClassifier
from utils import load_transcription, format_timecode, save_predictions
from typing import List, Tuple
import os

def predict_chroniques(base_model_path: str, hybrid_model_path: str, srt_file: str,
                       confidence_threshold: float = 0.4, # Seuil abaissé pour debug
                       min_chronique_duration: float = 5.0, # Durée abaissée pour debug
                       max_gap_duration: float = 2.0,
                       smoothing_window: int = 3) -> List[Tuple[float, float]]:
    """Prédit les chroniques avec le modèle Hybride (CamemBERT + Bi-LSTM + CRF)"""

    print(f"--- Diagnostic de prédiction (Hybride) ---")
    print(f"Base: {base_model_path}")
    print(f"Hybrid: {hybrid_model_path}")
    print(f"SRT: {srt_file}")

    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
    
    segments = load_transcription(srt_file)
    if not segments:
        print("Erreur: Aucun segment chargé.")
        return []
    print(f"Segments chargés: {len(segments)}")
    
    # Extraction des features (BERT inclus)
    X = base_extractor.prepare_features(segments, training=False)
    
    # Prédiction séquentielle
    # all_probs contient (N, 3) où les valeurs sont souvent 0 ou 1 grâce au CRF
    all_probs = hybrid_model.predict(X)
    pred_classes = np.argmax(all_probs, axis=1)
    
    print(f"Répartition des classes prédites :")
    print(f"  - Hors chronique (0) : {np.sum(pred_classes == 0)}")
    print(f"  - Début chronique (1) : {np.sum(pred_classes == 1)}")
    print(f"  - Dans chronique (2) : {np.sum(pred_classes == 2)}")
    
    # Probabilité d'être dans une chronique (classe 1 ou 2)
    probs = all_probs[:, 1] + all_probs[:, 2]
    
    # Lissage
    if smoothing_window > 1:
        smoothed_probs = np.convolve(probs, np.ones(smoothing_window)/smoothing_window, mode='same')
    else:
        smoothed_probs = probs
        
    # Grouper les segments
    raw_chroniques = []
    current_start = None
    
    for i, prob in enumerate(smoothed_probs):
        is_chronique = prob >= confidence_threshold
        # On utilise aussi le marqueur de début du CRF pour forcer une nouvelle chronique
        is_new_start = pred_classes[i] == 1
        
        if is_chronique:
            # Si le CRF dit "Nouveau début" alors qu'on était déjà "dedans", on coupe
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
        
    print(f"Blocs détectés avant filtrage: {len(raw_chroniques)}")
    
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
    
    if len(raw_chroniques) > 0 and len(final_chroniques) == 0:
        print("Alerte: Des chroniques ont été détectées mais elles étaient toutes trop courtes.")
        for s, e in raw_chroniques:
            print(f"  - Bloc ignoré: {format_timecode(s)} - {format_timecode(e)} (durée: {e-s:.1f}s)")
            
    return final_chroniques

if __name__ == "__main__":
    base_model = "models/radio_chronique_hybrid_base.pkl"
    hybrid_model = "models/radio_chronique_hybrid_hybrid.pt"
    # Chemin mis à jour pour correspondre à la réalité du projet
    srt_file = "../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/02_03_2026.srt"
    
    if not (os.path.exists(base_model) and os.path.exists(hybrid_model)):
        print("Modèles non trouvés. Veuillez d'abord lancer train.py.")
    elif not os.path.exists(srt_file):
        print(f"Fichier SRT non trouvé: {srt_file}")
    else:
        chroniques = predict_chroniques(base_model, hybrid_model, srt_file)
        print(f"\n=== RESULTAT FINAL ===")
        print(f"Chroniques validées: {len(chroniques)}")
        for i, (start, end) in enumerate(chroniques, 1):
            print(f"{i}: {format_timecode(start)} - {format_timecode(end)}")
        save_predictions(chroniques, "predictions_output.txt")
