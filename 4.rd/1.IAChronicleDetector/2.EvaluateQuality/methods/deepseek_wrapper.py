import os
import sys
import json
from datetime import datetime

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/10.DeepSeekChronicleDetector"))
sys.path.append(METHOD_DIR)

try:
    from detector import ChronicleDetector
    from transcriber import Transcriber
    from scrape_france_inter import get_chroniques
    from validator import ChronicleValidator
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_size="base", provider="kyutai", date_str=None):
        self.model_size = model_size
        self.provider = provider
        self.date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        
        # 1. Chargement dynamique des chroniques via le scraper
        print(f"[WRAPPER] Récupération de la grille France Inter ({self.date_str})...")
        self.chroniques_data = get_chroniques(self.date_str)
        if not self.chroniques_data:
            print("[WRAPPER] Alerte : Scraper vide, utilisation d'un prompt par défaut.")
            self.chroniques_data = [
                {"time": "07h00", "title": "Le journal de 7h"},
                {"time": "08h00", "title": "Le journal de 8h"},
                {"time": "08h20", "title": "L'invité de 8h20"}
            ]

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation réelle pour DeepSeek avec transcription Kyutai et validation.
        """
        # Initialisation du détecteur avec les données du scraper
        detector = ChronicleDetector(self.chroniques_data)
        
        # Initialisation du transcripteur (Kyutai par défaut)
        transcriber = Transcriber(model_size=self.model_size, provider=self.provider)
        
        # Initialisation du validateur
        validator = ChronicleValidator(self.chroniques_data)
        
        detections = []
        start_time_recording = "07:00" # Hypothèse par défaut pour l'évaluation
        
        print(f"[WRAPPER] Lancement de l'analyse via {self.provider.upper()}...")
        
        for segment in transcriber.transcribe_stream(audio_path):
            text = segment["text"]
            if not text:
                continue
            
            # Affichage de la phrase en cours
            print(f"[{segment['start']:>7.2f}s] {text}")
                
            # Analyse DeepSeek
            result = detector.analyze_sentence(text)
            
            if result.get("detecte"):
                chronique_name = result.get("chronique", "chronique")
                
                # Validation post-détection via la grille
                # Note: On passe segment["start"] car on est en "live" (speed=1.0)
                is_valid, status, wall_time, diff_str = validator.validate(
                    chronique_name, 
                    segment["start"], 
                    start_time_recording
                )
                
                print(f"\n>>> 🔔 IA DÉTECTION : {chronique_name.upper()}")
                print(f">>> VALIDATION : {status} ({diff_str} à {wall_time})")
                print(f">>> Raisonnement : {result.get('raisonnement')}\n")
                
                if is_valid:
                    detections.append({
                        "label": chronique_name,
                        "start": segment["start"],
                        "end": segment.get("end", segment["start"] + 5.0),
                        "detected_at": segment["start"],
                        "confidence": 0.9,
                        "wall_time": wall_time,
                        "reasoning": result.get("raisonnement")
                    })
                else:
                    print(f">>> ❌ DÉTECTION REJETÉE PAR LE VALIDATEUR\n")
        
        return detections
