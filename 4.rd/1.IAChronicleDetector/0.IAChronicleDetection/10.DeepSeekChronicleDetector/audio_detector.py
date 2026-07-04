import os
import sys
import json
import argparse
from datetime import datetime

from scrape_france_inter import get_chroniques
from detector import ChronicleDetector
from audio_processor import accelerate_audio, map_timestamp, format_timestamp
from transcriber import Transcriber
from validator import ChronicleValidator

def main():
    parser = argparse.ArgumentParser(description="Détection de chroniques radio dans un fichier audio.")
    parser.add_argument("audio_path", help="Chemin vers le fichier audio (mp3, wav, etc.)")
    parser.add_argument("--speed", type=float, default=1.0, help="Facteur d'accélération (ex: 2.0)")
    parser.add_argument("--date", help="Date de l'émission au format YYYY-MM-DD (par défaut: aujourd'hui)")
    parser.add_argument("--start-time", default="07:00", help="Heure de début de l'enregistrement (ex: 07:00)")
    parser.add_argument("--model", default="base", help="Taille du modèle Whisper (tiny, base, small, medium, large-v3)")
    parser.add_argument("--output", default="detections_audio.json", help="Fichier de sortie JSON")
    
    args = parser.parse_args()

    if not args.date:
        args.date = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(args.audio_path):
        print(f"[ERREUR] Le fichier {args.audio_path} n'existe pas.")
        sys.exit(1)

    # 1. Chargement de la grille des programmes
    print(f"\n[1/4] Récupération de la grille France Inter ({args.date})...")
    chroniques_data = get_chroniques(args.date)
    if not chroniques_data:
        print("[ALERTE] Aucune chronique récupérée, utilisation d'une liste par défaut.")
        chroniques_data = [
            {"time": "07h00", "title": "Le journal de 7h"},
            {"time": "08h00", "title": "Le journal de 8h"},
            {"time": "08h20", "title": "L'invité de 8h20"}
        ]
    
    print(f"--- {len(chroniques_data)} chroniques trouvées pour le {args.date} ---")
    for c in chroniques_data:
        print(f"  - {c['time']} : {c['title']}")
    print("-" * 30)
    
    # 2. Préparation de l'audio
    print(f"\n[2/4] Préparation de l'audio...")
    processed_audio, is_temp = accelerate_audio(args.audio_path, args.speed)

    try:
        # 3. Initialisation des modules
        print(f"\n[3/4] Initialisation des modèles IA et du validateur...")
        transcriber = Transcriber(model_size=args.model)
        detector = ChronicleDetector(chroniques_data)
        validator = ChronicleValidator(chroniques_data)
        
        detections = []
        
        # 4. Traitement en flux
        print(f"\n[4/4] Analyse en cours (Heure de début : {args.start_time})...")
        print("-" * 100)
        print(f"{'HEURE':<8} | {'CHRONIQUE':<25} | {'ÉCART':<8} | {'STATUT'}")
        print("-" * 100)
        
        for segment in transcriber.transcribe_stream(processed_audio):
            text = segment["text"]
            if not text:
                continue
                
            result = detector.analyze_sentence(text)
            
            if result.get("detecte"):
                chronique_name = result.get("chronique")
                
                # Calcul du timestamp original (secondes écoulées)
                orig_seconds = map_timestamp(segment["start"], args.speed)
                
                # Validation via la grille
                is_valid, status, wall_time, diff_str = validator.validate(
                    chronique_name, 
                    orig_seconds, 
                    args.start_time
                )
                
                print(f"{wall_time:<8} | {chronique_name[:25]:<25} | {diff_str:<8} | {status}")
                
                if is_valid:
                    detections.append({
                        "wall_time": wall_time,
                        "audio_timestamp": format_timestamp(orig_seconds),
                        "chronique": chronique_name,
                        "diff": diff_str,
                        "text": text
                    })

        # Sauvegarde des résultats
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({
                "file": args.audio_path,
                "date": args.date,
                "speed": args.speed,
                "start_time": args.start_time,
                "detections": detections
            }, f, ensure_ascii=False, indent=2)
            
        if detections:
            print("\n" + "="*60)
            print("   RÉSUMÉ DES CHRONIQUES VALIDÉES")
            print("="*60)
            print(f"{'HEURE':<8} | {'CHRONIQUE':<30} | {'ÉCART'}")
            print("-" * 60)
            for d in detections:
                print(f"{d['wall_time']:<8} | {d['chronique'][:30]:<30} | {d['diff']}")
            print("="*60)
        else:
            print("\nAucune chronique n'a été validée.")

    finally:
        # Nettoyage
        if is_temp and os.path.exists(processed_audio):
            print(f"\n[CLEANUP] Suppression du fichier temporaire : {processed_audio}")
            os.remove(processed_audio)

if __name__ == "__main__":
    main()
