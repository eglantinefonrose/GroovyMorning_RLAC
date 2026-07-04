import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/10.DeepSeekChronicleDetector"))
sys.path.append(METHOD_DIR)

try:
    from detector import ChronicleDetector
    from transcriber import Transcriber
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_size="base", prompt=None):
        self.model_size = model_size
        # Prompt par défaut pour France Inter comme dans evaluate_quality.py
        self.prompt = prompt or ["Le journal de 7h", "Le journal de 8h", "L'invité de 8h20"]

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation réelle pour DeepSeek.
        """
        detector = ChronicleDetector(self.prompt)
        transcriber = Transcriber(model_size=self.model_size)
        
        detections = []
        
        # On utilise transcribe_stream pour simuler le flux comme dans l'original
        for segment in transcriber.transcribe_stream(audio_path):
            text = segment["text"]
            if not text:
                continue
            
            # Affichage de la phrase en cours de lecture
            print(f"[{segment['start']:>7.2f}s] {text}")
                
            result = detector.analyze_sentence(text)
            
            if result.get("detecte"):
                label = result.get("chronique", "chronique")
                print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE : {label.upper()}")
                print(f">>> Raisonnement : {result.get('raisonnement')}\n")
                
                detections.append({
                    "label": result.get("chronique", "chronique"),
                    "start": segment["start"],
                    "end": segment.get("end", segment["start"] + 5.0), # Estimation si end manque
                    "detected_at": segment["start"],
                    "confidence": 0.9
                })
        
        return detections
