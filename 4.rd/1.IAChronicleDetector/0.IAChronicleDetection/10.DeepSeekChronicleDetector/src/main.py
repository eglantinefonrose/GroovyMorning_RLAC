"""
Détection de début de chroniques en flux réel ou simulé via DeepSeek avec Validation.
"""

import os
import json
import re
import time
import sys
import argparse
import signal
import requests
from datetime import datetime, timedelta
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

# Global for signal handling
ALL_DETECTIONS = []
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_JSON = os.path.join(BASE_DIR, "detections_live_deepseek.json")
LOG_FILE = os.path.join(BASE_DIR, "session_log.txt")

def signal_handler(sig, frame):
    print("\n[INFO] Interruption reçue. Sauvegarde des résultats...")
    save_results()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def save_results():
    if ALL_DETECTIONS:
        # On retourne uniquement la liste d'objets comme demandé
        output_data = [
            {
                "label": d["label"],
                "start": round(d["start"], 2),
                "end": round(d["end"], 2),
                "detected_at": round(d["detected_at"], 2),
                "confidence": d["confidence"]
            } for d in ALL_DETECTIONS
        ]
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"[OK] Résultats au format JSON sauvegardés dans {OUTPUT_JSON}")
    else:
        print("[INFO] Aucune détection à sauvegarder.")

def get_sentences_from_file(file_path):
    """Lit le fichier texte et retourne un générateur de phrases."""
    print(f"Lecture du fichier texte : {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"Erreur : le fichier {file_path} est introuvable.")
        return
    
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    for s in sentences:
        if s.strip():
            yield {"text": s.strip(), "start": 0} # Pas de timestamp pour le texte simple

def process_stream(segment_gen, detector, validator, start_time="07:00", is_audio=True, dry_run=False):
    """Traite les segments de transcription un par un."""
    print("-" * 100)
    print(f"{'HEURE':<8} | {'CHRONIQUE':<25} | {'ÉCART':<8} | {'STATUT'}")
    print("-" * 100)
    
    if dry_run:
        print("[MODE SIMULATION] La détection DeepSeek est désactivée.")

    with open(LOG_FILE, "w", encoding="utf-8") as log_f:
        simulated_seconds = 0
        phrase_count = 0

        for segment in segment_gen:
            phrase_count += 1
            current_sentence = segment["text"]
            
            # Si c'est de l'audio, on utilise le timestamp réel, sinon on estime
            if is_audio and "start" in segment and segment["start"] is not None:
                simulated_seconds = segment["start"]
            else:
                simulated_seconds += 5 # Estimation pour le texte

            # Affichage en temps réel de la phrase avec timestamp
            time_str = f"[{int(simulated_seconds // 60):02d}:{int(simulated_seconds % 60):02d}]"
            print(f"{time_str} > {current_sentence}")
            log_f.write(f"{time_str} Traitement phrase {phrase_count}: {current_sentence}\n")
            log_f.flush()

            if dry_run:
                continue

            # Analyse via DeepSeek
            result = detector.analyze_sentence(current_sentence)
            
            if result.get("detecte"):
                chronique_name = result.get("chronique")
                reasoning = result.get("raisonnement") or result.get("reasoning")
                
                # Validation via la grille
                is_valid, status, wall_time, diff_str = validator.validate(
                    chronique_name, 
                    simulated_seconds, 
                    start_time
                )
                
                msg = f"[DÉTECTION] 🔔 {chronique_name} | {status} | {wall_time} ({diff_str})"
                print(f"\033[92m{msg}\033[0m") # En vert
                log_f.write(f"{msg}\nReasoning: {reasoning}\n")
                log_f.flush()
                
                if is_valid:
                    # 'start' est le début de la phrase qui a déclenché la détection
                    # 'detected_at' est le moment de la détection (la fin du segment/phrase)
                    # 'end' est mis par défaut à start + 60s (ou fin du segment) pour représenter un bloc
                    ALL_DETECTIONS.append({
                        "label": chronique_name,
                        "start": segment.get("start", simulated_seconds),
                        "end": segment.get("end", simulated_seconds + 5.0),
                        "detected_at": segment.get("start", simulated_seconds),
                        "confidence": 1.0 # DeepSeek est considéré comme binaire/confiant ici
                    })
            
    if dry_run:
        print(f"\nFin de la simulation. {phrase_count} phrases transcrites.")
    else:
        print(f"\nFin du flux. {len(ALL_DETECTIONS)} chroniques validées.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Détection de chroniques Live ou Simulation")
    parser.add_argument("--audio", help="Chemin vers un fichier audio (ou '-' pour stdin)")
    parser.add_argument("--file", help="Fichier texte de transcription")
    parser.add_argument("--provider", default="kyutai_stt", choices=["whisper", "kyutai", "kyutai_mlx", "kyutai_stt"], help="Fournisseur de transcription")
    parser.add_argument("--model", default="base", help="Modèle Whisper")
    parser.add_argument("--start-time", default="07:00", help="Heure de début de l'émission (ex: 07:00)")
    parser.add_argument("--output", default="detections_live_deepseek.json", help="Fichier JSON de sortie")
    parser.add_argument("--date", help="Date de l'émission (YYYY-MM-DD), défaut: aujourd'hui")
    parser.add_argument("--language", default="fr", help="Langue de transcription (ex: fr, en)")
    parser.add_argument("--simu", action="store_true", help="Mode simulation : transcription uniquement, pas d'appels API DeepSeek")
    
    args = parser.parse_args()
    OUTPUT_JSON = args.output

    # 1. Chargement dynamique des chroniques
    date_display = args.date if args.date else "aujourd'hui"
    print(f"Chargement dynamique des chroniques France Inter ({date_display})...")
    CHRONIQUES_DATA = get_chroniques(args.date)

    if not CHRONIQUES_DATA:
        print("[ALERTE] Aucune chronique récupérée, utilisation d'une liste par défaut.")
        CHRONIQUES_DATA = [
            {"time": "07h00", "title": "Le journal de 7h"},
            {"time": "08h00", "title": "Le journal de 8h"},
            {"time": "08h20", "title": "L'invité de 8h20"}
        ]

    # 2. Initialisation des composants
    detector = ChronicleDetector(CHRONIQUES_DATA)
    validator = ChronicleValidator(CHRONIQUES_DATA)

    # 3. Acquisition et traitement
    try:
        if args.audio:
            transcriber = Transcriber(provider=args.provider, model_size=args.model)
            segment_gen = transcriber.transcribe_stream(args.audio, language=args.language)
            process_stream(segment_gen, detector, validator, args.start_time, is_audio=True, dry_run=args.simu)
        elif args.file:
            segment_gen = get_sentences_from_file(args.file)
            process_stream(segment_gen, detector, validator, args.start_time, is_audio=False, dry_run=args.simu)
        else:
            # Par défaut, si rien n'est spécifié, on prend full_show_transcription.txt si il existe
            default_file = os.path.join(BASE_DIR, "full_show_transcription.txt")
            if os.path.exists(default_file):
                print(f"Utilisation par défaut de {default_file}")
                segment_gen = get_sentences_from_file(default_file)
                process_stream(segment_gen, detector, validator, args.start_time, is_audio=False, dry_run=args.simu)
            else:
                parser.print_help()
                sys.exit(1)
    except KeyboardInterrupt:
        pass # Géré par le signal handler
    finally:
        if not args.simu:
            save_results()
            
            print("\n--- Analyse de cohérence finale ---")
            from check_schedule import compare_with_schedule, parse_deepseek_output
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                detections_to_check = parse_deepseek_output(content)
                if detections_to_check:
                    compare_with_schedule(detections_to_check)

