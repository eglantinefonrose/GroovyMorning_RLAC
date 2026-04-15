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

    # Force CPU pour la stabilité (évite les bugs CRF sur MPS/M1)
    hybrid_model.device = torch.device('cpu')
    hybrid_model.model.to(torch.device('cpu'))

    segments = load_transcription(srt_file)
    if not segments:
        print("Erreur: Aucun segment chargé.")
        return []
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
            # On applique le dropout (même si eval() le désactive, on suit la structure)
            emissions = hybrid_model.model.fc(hybrid_model.model.dropout(lstm_out))
            all_emissions_list.append(emissions.cpu().numpy()[0])
            
            # Décodage CRF classique pour la décision finale
            chunk_preds = hybrid_model.model.crf.decode(emissions)[0]

            # Vote majoritaire simple pour le recouvrement
            for j, p in enumerate(chunk_preds):
                if i + j < len(X):
                    all_preds[i+j] = p

    # --- DIAGNOSTIC DES SCORES BRUTS ---
    if all_emissions_list:
        emissions_stack = np.vstack(all_emissions_list)
        print(f"\n--- Diagnostic des Scores Bruts (Logits) ---")
        print(f"Moyenne Score Classe 0 (Hors) : {np.mean(emissions_stack[:, 0]):.4f}")
        print(f"Moyenne Score Classe 1 (Début): {np.mean(emissions_stack[:, 1]):.4f}")
        print(f"Moyenne Score Classe 2 (Dans) : {np.mean(emissions_stack[:, 2]):.4f}")
        
        max_scores = np.max(emissions_stack, axis=0)
        print(f"Scores Maximums atteints :")
        print(f"  - Classe 0 : {max_scores[0]:.4f}")
        print(f"  - Classe 1 : {max_scores[1]:.4f}")
        print(f"  - Classe 2 : {max_scores[2]:.4f}")
        
        # Combien de segments préfèrent (brut) la classe 1 ou 2 ?
        raw_preferences = np.argmax(emissions_stack, axis=1)
        print(f"Préférences brutes (sans contraintes CRF) :")
        print(f"  - Segments penchant pour 1 ou 2 : {np.sum(raw_preferences > 0)} / {len(emissions_stack)}")

    pred_classes = all_preds
    # Pour garder la compatibilité avec le reste du script
    all_probs = np.zeros((len(pred_classes), 3))
    for i, v in enumerate(pred_classes):
        all_probs[i, v] = 1.0
    
    # Probabilité d'être dans une chronique (classe 1 ou 2)
    probs = all_probs[:, 1] + all_probs[:, 2]
    
    print(f"Statistiques des probabilités brutes :")
    print(f"  - Min : {np.min(probs):.4f}")
    print(f"  - Max : {np.max(probs):.4f}")
    print(f"  - Moyenne : {np.mean(probs):.4f}")
    print(f"  - Nombre de segments > seuil ({confidence_threshold}) : {np.sum(probs >= confidence_threshold)}")

    print(f"Répartition des classes prédites par le CRF :")
    print(f"  - Hors chronique (0) : {np.sum(pred_classes == 0)}")
    print(f"  - Début chronique (1) : {np.sum(pred_classes == 1)}")
    print(f"  - Dans chronique (2) : {np.sum(pred_classes == 2)}")
    
    # Lissage
    if smoothing_window > 1:
        smoothed_probs = np.convolve(probs, np.ones(smoothing_window)/smoothing_window, mode='same')
        print(f"Lissage appliqué (fenêtre {smoothing_window})")
    else:
        smoothed_probs = probs
        
    # Grouper les segments
    raw_chroniques = []
    current_start = None
    
    print("\n--- Analyse du flux des segments ---")
    for i, prob in enumerate(smoothed_probs):
        is_chronique = prob >= confidence_threshold
        is_new_start = pred_classes[i] == 1
        
        if is_chronique:
            if is_new_start and current_start is not None:
                print(f"  [CRF] Nouveau début détecté à {format_timecode(segments[i]['start'])}. Fermeture bloc précédent.")
                raw_chroniques.append((current_start, segments[i-1]['end']))
                current_start = segments[i]['start']
            
            if current_start is None:
                print(f"  [DETECTION] Début de bloc à {format_timecode(segments[i]['start'])} (prob: {prob:.2f})")
                current_start = segments[i]['start']
            else:
                if i > 0 and (segments[i]['start'] - segments[i-1]['end']) > max_gap_duration:
                    print(f"  [GAP] Trou de {segments[i]['start'] - segments[i-1]['end']:.1f}s détecté à {format_timecode(segments[i]['start'])}. Scission.")
                    raw_chroniques.append((current_start, segments[i-1]['end']))
                    current_start = segments[i]['start']
        else:
            if current_start is not None:
                print(f"  [FIN] Fin de bloc à {format_timecode(segments[i-1]['end'])} (prob tombe à {prob:.2f})")
                raw_chroniques.append((current_start, segments[i-1]['end']))
                current_start = None
                
    if current_start is not None:
        raw_chroniques.append((current_start, segments[-1]['end']))
        
    print(f"\nBlocs bruts détectés : {len(raw_chroniques)}")
    
    # Fusionner les blocs très proches
    merged_chroniques = []
    if raw_chroniques:
        curr_start, curr_end = raw_chroniques[0]
        for i in range(1, len(raw_chroniques)):
            next_start, next_end = raw_chroniques[i]
            if next_start - curr_end <= max_gap_duration:
                print(f"  [FUSION] Fusion de deux blocs à {format_timecode(next_start)}")
                curr_end = next_end
            else:
                merged_chroniques.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged_chroniques.append((curr_start, curr_end))
    
    # Filtrer par durée
    print(f"Filtrage par durée minimale : {min_chronique_duration}s")
    final_chroniques = []
    for s, e in merged_chroniques:
        duration = e - s
        if duration >= min_chronique_duration:
            final_chroniques.append((s, e))
        else:
            print(f"  [REJET] Bloc {format_timecode(s)}-{format_timecode(e)} rejeté car trop court ({duration:.1f}s)")
            
    return final_chroniques

if __name__ == "__main__":
    base_model = "models/radio_chronique_hybrid_base.pkl"
    hybrid_model = "models/radio_chronique_hybrid_hybrid.pt"
    # Chemin mis à jour pour correspondre à la réalité du projet
    srt_file = "../../@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/26811-06.04.2026-ITEMA_24466243-2026F10761S0096-NET_MFI_8F75AA4E-79C7-4CF3-A0B7-2D7EBC1FB5B5-22-534f5f6ae83fc95044c42304b90ca1f7_transcription.srt"
    
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
