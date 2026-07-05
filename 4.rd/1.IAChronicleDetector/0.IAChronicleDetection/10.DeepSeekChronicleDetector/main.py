"""
Détection de début de chroniques en flux simulé via DeepSeek avec Validation.
"""

import os
import json
import re
import time
import sys
import argparse
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

from scrape_france_inter import get_chroniques
from detector import ChronicleDetector
from validator import ChronicleValidator
from transcriber import Transcriber

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    print("[ERREUR] La variable d'environnement DEEPSEEK_API_KEY n'est pas définie.")
    sys.exit(1)

def get_sentences_from_audio(audio_path, provider="whisper", model_size="base"):
    """Transcrit l'audio et retourne une liste de phrases."""
    print(f"Transcription de l'audio ({provider}) : {audio_path}...")
    transcriber = Transcriber(provider=provider, model_size=model_size)
    sentences = []
    for segment in transcriber.transcribe_stream(audio_path):
        text = segment["text"].strip()
        if text:
            sentences.append(text)
    return sentences

def get_sentences_from_file(file_path):
    """Lit le fichier texte et retourne une liste de phrases."""
    print(f"Lecture du fichier texte : {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"Erreur : le fichier {file_path} est introuvable.")
        return []
    
    # Découpage simple en phrases
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    return [s.strip() for s in sentences if s.strip()]

def simulate_stream(sentences, detector, validator, start_time="07:00"):
    """Simule l'arrivée des phrases une par une."""
    if not sentences:
        print("Aucune phrase à traiter.")
        return []
    
    print(f"Simulation lancée : {len(sentences)} phrases à traiter.")
    print("-" * 100)
    print(f"{'HEURE':<8} | {'CHRONIQUE':<25} | {'ÉCART':<8} | {'STATUT'}")
    print("-" * 100)
    
    detections = []
    # Pour la simulation, on simule une progression de 5 secondes par phrase.
    simulated_seconds = 0

    for i, current_sentence in enumerate(sentences):
        result = detector.analyze_sentence(current_sentence)
        simulated_seconds += 5 # Estimation
        
        if result.get("detecte"):
            chronique_name = result.get("chronique")
            
            # Validation via la grille
            is_valid, status, wall_time, diff_str = validator.validate(
                chronique_name, 
                simulated_seconds, 
                start_time
            )
            
            print(f"{wall_time:<8} | {chronique_name[:25]:<25} | {diff_str:<8} | {status}")
            
            if is_valid:
                detections.append({
                    "index": i,
                    "wall_time": wall_time,
                    "chronique": chronique_name,
                    "simulated_seconds": simulated_seconds,
                    "result": result
                })
            
    print(f"\nFin de la simulation. {len(detections)} chroniques validées.")
    return detections

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Détection de chroniques (Simulation ou Audio)")
    parser.add_argument("--audio", help="Chemin vers un fichier audio à transcrire et analyser")
    parser.add_argument("--file", default="full_show_transcription.txt", help="Fichier texte de transcription (par défaut: full_show_transcription.txt)")
    parser.add_argument("--provider", default="whisper", choices=["whisper", "kyutai", "kyutai_mlx"], help="Fournisseur de transcription (whisper, kyutai ou kyutai_mlx)")
    parser.add_argument("--model", default="base", help="Modèle Whisper (si --audio est utilisé)")
    parser.add_argument("--start-time", default="07:00", help="Heure de début de l'émission (ex: 07:00)")
    
    args = parser.parse_args()

    # 1. Chargement dynamique des chroniques
    print("Chargement dynamique des chroniques France Inter...")
    CHRONIQUES_DATA = get_chroniques()

    if not CHRONIQUES_DATA:
        print("[ALERTE] Aucune chronique récupérée, utilisation d'une liste par défaut.")
        CHRONIQUES_DATA = [
            {"time": "07h00", "title": "Le journal de 7h"},
            {"time": "08h00", "title": "Le journal de 8h"},
            {"time": "08h20", "title": "L'invité de 8h20"}
        ]

    # 2. Acquisition des phrases
    if args.audio:
        sentences = get_sentences_from_audio(args.audio, args.provider, args.model)
    else:
        sentences = get_sentences_from_file(args.file)

    # 3. Initialisation des composants et simulation
    detector = ChronicleDetector(CHRONIQUES_DATA)
    validator = ChronicleValidator(CHRONIQUES_DATA)

    all_detections = simulate_stream(sentences, detector, validator, args.start_time)
    
    if all_detections:
        output_data = {
            "detections": [
                {
                    "label": d["chronique"],
                    "start": d["simulated_seconds"],
                    "end": d["simulated_seconds"] + 5.0, # Estimation
                    "detected_at": d["simulated_seconds"],
                    "confidence": 0.9,
                    "wall_time": d["wall_time"],
                    "reasoning": d["result"].get("reasoning") or d["result"].get("raisonnement")
                } for d in all_detections
            ],
            "metrics": {
                "total_detected": len(all_detections)
            }
        }
        with open("detections_live_deepseek.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"Résultats détaillés sauvegardés dans detections_live_deepseek.json")
