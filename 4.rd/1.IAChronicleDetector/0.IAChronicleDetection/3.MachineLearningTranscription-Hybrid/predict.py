import numpy as np
import torch
import time
from train import RadioChroniqueClassifier, HybridSequenceClassifier
from utils import load_transcription, format_timecode, save_predictions, calculate_quality_score, load_timecodes
from typing import List, Tuple
import os

def predict_chroniques(base_model_path: str, hybrid_model_path: str, srt_file: str,
                       confidence_threshold: float = 0.4, # Seuil abaissé pour debug
                       min_chronique_duration: float = 5.0, # Durée abaissée pour debug
                       max_gap_duration: float = 2.0,
                       smoothing_window: int = 3,
                       gt_file: str = None) -> Tuple[List[Tuple[float, float]], dict]:
    """Prédit les chroniques avec le modèle Hybride (CamemBERT + Bi-LSTM + CRF)"""

    start_time = time.time()
    print(f"--- Diagnostic de prédiction (Hybride) ---")
    print(f"Base: {base_model_path}")
    print(f"Hybrid: {hybrid_model_path}")
    print(f"SRT: {srt_file}")
    
    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)

    # Force CPU pour la stabilité (évite les bugs CRF sur MPS/M1)
    hybrid_model.device = torch.device('cpu')
    hybrid_model.model.to(torch.device('cpu'))

    segments = load_transcription(srt_file)
    if not segments:
        print("Erreur: Aucun segment chargé.")
        return [], {}
    print(f"Segments chargés: {len(segments)}")

    # Extraction des features (BERT inclus)
    X = base_extractor.prepare_features(segments, training=False)

    # Prédiction par fenêtres pour éviter la saturation sur de longues séquences
    print("Prédiction en cours (par fenêtres)...")
    seq_len = hybrid_model.seq_len
    all_preds = np.zeros(len(X), dtype=int)
    all_emissions_list = []

    # On avance par demi-fenêtre pour avoir un recouvrement
    step = seq_len // 2
    
    hybrid_model.model.eval()
    with torch.no_grad():
        for i in range(0, len(X), step):
            end_idx = min(i + seq_len, len(X))
            if end_idx - i < 2: continue # Trop court

            x_chunk = torch.FloatTensor(X[i:end_idx]).unsqueeze(0).to(hybrid_model.device)
            
            # Accès direct aux couches pour récupérer les scores bruts (émissions)
            lstm_out, _ = hybrid_model.model.lstm(x_chunk)
            emissions = hybrid_model.model.fc(hybrid_model.model.dropout(lstm_out))
            all_emissions_list.append(emissions.cpu().numpy()[0])
            
            chunk_preds = hybrid_model.model.crf.decode(emissions)[0]

            for j, p in enumerate(chunk_preds):
                if i + j < len(X):
                    all_preds[i+j] = p

    pred_classes = all_preds
    all_probs = np.zeros((len(pred_classes), 3))
    for i, v in enumerate(pred_classes):
        all_probs[i, v] = 1.0
    
    probs = all_probs[:, 1] + all_probs[:, 2]
    
    if smoothing_window > 1:
        smoothed_probs = np.convolve(probs, np.ones(smoothing_window)/smoothing_window, mode='same')
    else:
        smoothed_probs = probs
        
    raw_chroniques = []
    current_start = None
    
    for i, prob in enumerate(smoothed_probs):
        is_chronique = prob >= confidence_threshold
        is_new_start = pred_classes[i] == 1
        
        if is_chronique:
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
    base_model = "models/radio_chronique_hybrid_base.pkl"
    hybrid_model = "models/radio_chronique_hybrid_hybrid.pt"
    # Chemin mis à jour pour correspondre à la réalité du projet
    srt_file = "../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_transcription.srt"
    gt_file = "../../@assets/1.modelOutputs/1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_timecode_chronique.txt"

    if not (os.path.exists(base_model) and os.path.exists(hybrid_model)):
        print("Modèles non trouvés. Veuillez d'abord lancer train.py.")
    elif not os.path.exists(srt_file):
        print(f"Fichier SRT non trouvé: {srt_file}")
    else:
        chroniques, quality = predict_chroniques(base_model, hybrid_model, srt_file, gt_file=gt_file)
        print(f"\n=== RESULTAT FINAL (HYBRIDE) ===")
        print(f"Chroniques validées: {len(chroniques)}")
        for i, (start, end) in enumerate(chroniques, 1):
            print(f"{i}: {format_timecode(start)} - {format_timecode(end)}")
            
        if quality:
            print(f"\n=== NOTE DE QUALITÉ : {quality['total_score']}/100 ===")
            print(f"Détails :")
            for k, v in quality['details'].items():
                print(f"  - {k}: {v}")
                
        save_predictions(chroniques, "predictions_output.txt")
