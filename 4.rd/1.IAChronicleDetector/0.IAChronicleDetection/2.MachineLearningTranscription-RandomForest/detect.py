import argparse
import json
import sys
import os
import re
import time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
from train import RadioChroniqueClassifier
from utils import extract_features_from_text, format_timecode

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

def predict_chroniques(model_path, segments, confidence_threshold=0.5):
    """Prédit les chroniques à partir des segments transcrits"""
    classifier = RadioChroniqueClassifier.load_model(model_path)
    
    if not segments:
        return []
    
    X = classifier.prepare_features(segments, training=False)
    
    if len(classifier.classifier.classes_) == 1:
        if classifier.classifier.classes_[0] == 1:
            probs = np.ones(len(X))
        else:
            probs = np.zeros(len(X))
    else:
        probs = classifier.classifier.predict_proba(X)[:, 1]
    
    # Lissage simple
    smoothed_probs = np.convolve(probs, np.ones(3)/3, mode='same')
    
    detected_chroniques = []
    current_start = None
    current_end = None
    max_conf = 0
    
    for i, prob in enumerate(smoothed_probs):
        if prob >= confidence_threshold:
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

def live_detection(audio_path, model_path, whisper_model_size="base", chunk_duration=15, confidence_threshold=0.5):
    """Simule une détection live en traitant le fichier par blocs"""
    import librosa
    
    print(f"Démarrage de la détection live (simulée) sur : {audio_path}")
    classifier = RadioChroniqueClassifier.load_model(model_path)
    whisper_model = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")
    
    # Charger l'audio
    audio, sr = librosa.load(audio_path, sr=16000)
    chunk_samples = int(chunk_duration * sr)
    
    all_segments = []
    
    for start_sample in range(0, len(audio), chunk_samples):
        end_sample = min(start_sample + chunk_samples, len(audio))
        chunk = audio[start_sample:end_sample]
        current_offset = start_sample / sr
        
        print(f"\n--- Traitement bloc {format_timecode(current_offset)} ---")
        
        # Transcription du chunk
        segments_gen, _ = whisper_model.transcribe(chunk, beam_size=5, language="fr")
        
        new_segments_in_chunk = []
        for s in segments_gen:
            seg = {
                'start': current_offset + s.start,
                'end': current_offset + s.end,
                'text': s.text.strip()
            }
            new_segments_in_chunk.append(seg)
            print(f"  [{format_timecode(seg['start'])} - {format_timecode(seg['end'])}] {seg['text']}")
            
        if not new_segments_in_chunk:
            continue
            
        all_segments.extend(new_segments_in_chunk)
        
        # Prédiction sur l'ensemble des segments accumulés
        X = classifier.prepare_features(all_segments, training=False)
        probs = classifier.classifier.predict_proba(X)[:, 1]
        
        # Affichage des probabilités pour les nouveaux segments
        last_probs = probs[-len(new_segments_in_chunk):]
        for i, p in enumerate(last_probs):
            if p >= confidence_threshold:
                print(f"  >>> CHRONIQUE DÉTECTÉE (Conf: {p:.2f})")
                
        # Simuler le temps réel (optionnel, pour l'affichage)
        # time.sleep(chunk_duration / 10) # 10x plus vite que le réel pour le test

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche ML Transcription RF)")
    parser.add_argument("audio", help="Chemin vers le fichier audio")
    parser.add_argument("--model", default="models/radio_chronique_rf.pkl", help="Chemin vers le modèle")
    parser.add_argument("--threshold", type=float, default=0.5, help="Seuil de confiance")
    parser.add_argument("--whisper-model", default="base", help="Taille du modèle Whisper")
    parser.add_argument("--live", action="store_true", help="Active le mode détection live simulée")
    parser.add_argument("--chunk-size", type=int, default=30, help="Taille du chunk audio en secondes pour le mode live")
    
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)
        
    if args.live:
        live_detection(
            args.audio, 
            args.model, 
            whisper_model_size=args.whisper_model, 
            chunk_duration=args.chunk_size,
            confidence_threshold=args.threshold
        )
    else:
        segments = transcribe_audio(args.audio, model_size=args.whisper_model)
        results = predict_chroniques(args.model, segments, confidence_threshold=args.threshold)
        print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
