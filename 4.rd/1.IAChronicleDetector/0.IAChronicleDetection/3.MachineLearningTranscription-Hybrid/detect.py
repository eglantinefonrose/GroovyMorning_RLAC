import argparse
import json
import sys
import os
from pathlib import Path
import numpy as np
import torch
from faster_whisper import WhisperModel
from train import RadioChroniqueClassifier, HybridSequenceClassifier

def transcribe_audio(audio_path, model_size="base"):
    """Transcrire l'audio en segments compatibles avec le classifier"""
    print(f"Transcription de {audio_path} avec Whisper ({model_size})...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, language="fr")
    
    formatted_segments = []
    for segment in segments:
        formatted_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip()
        })
    return formatted_segments

def predict_chroniques(base_model_path, hybrid_model_path, segments):
    """Prédit les chroniques avec le modèle Hybride"""
    if not segments:
        return []

    base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
    hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
    
    # Force CPU pour la stabilité
    hybrid_model.device = torch.device('cpu')
    hybrid_model.model.to(torch.device('cpu'))
    
    X = base_extractor.prepare_features(segments, training=False)
    
    hybrid_model.model.eval()
    with torch.no_grad():
        # Transformation en tenseur
        X_tensor = torch.FloatTensor(X).unsqueeze(0).to(hybrid_model.device)
        # Prédiction (CRF decode)
        preds = hybrid_model.model.decode(X_tensor)[0]
        # Probabilités (approximatives via emission scores si possible, mais on va utiliser les labels du CRF)
        emissions = hybrid_model.model.emissions(X_tensor)
        probs = torch.softmax(emissions, dim=2)[0, :, 1].cpu().numpy()

    detected_chroniques = []
    current_start = None
    current_end = None
    max_conf = 0
    
    for i, label in enumerate(preds):
        prob = probs[i]
        if label > 0: # 1 ou 2 selon le modèle
            if current_start is None:
                current_start = segments[i]['start']
            current_end = segments[i]['end']
            max_conf = max(max_conf, prob)
        else:
            if current_start is not None:
                if current_end - current_start >= 5.0:
                    detected_chroniques.append({
                        "start": round(current_start, 2),
                        "end": round(current_end, 2),
                        "label": "chronique",
                        "confidence": round(float(max_conf), 3)
                    })
                current_start = None
                max_conf = 0
                
    if current_start is not None:
        if current_end - current_start >= 5.0:
            detected_chroniques.append({
                "start": round(current_start, 2),
                "end": round(current_end, 2),
                "label": "chronique",
                "confidence": round(float(max_conf), 3)
            })
            
    return detected_chroniques

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche ML Transcription Hybride)")
    parser.add_argument("audio", help="Chemin vers le fichier audio")
    parser.add_argument("--base-model", default="models/radio_chronique_hybrid_base.pkl", help="Modèle base")
    parser.add_argument("--hybrid-model", default="models/radio_chronique_hybrid_hybrid.pt", help="Modèle hybride")
    parser.add_argument("--whisper-model", default="base", help="Taille du modèle Whisper")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)
        
    segments = transcribe_audio(args.audio, model_size=args.whisper_model)
    results = predict_chroniques(args.base_model, args.hybrid_model, segments)
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
