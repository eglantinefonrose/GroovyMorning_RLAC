import os
import sys
import json
import librosa
import numpy as np

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/1.MachineLearningAudio"))
sys.path.append(METHOD_DIR)
sys.path.append(os.path.join(METHOD_DIR, 'src'))

try:
    from logic import ChronicleClassifier
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_path=None, threshold=0.89):
        self.model_path = model_path or os.path.join(METHOD_DIR, "models/rlac-audio-segmenter-chroniques_model.pkl")
        self.threshold = threshold

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard.
        Cette approche traite directement l'audio.
        """
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at {self.model_path}")
            return []

        classifier = ChronicleClassifier()
        classifier.load_model(self.model_path)
        
        # On simule le passage du temps par fenêtres de 1 seconde
        print("[INFO] Simulation du flux audio...")
        
        # Pour ML Audio, la détection est faite par fenêtrage
        raw_segments = classifier.detect_chronicles_in_file(
            audio_path, 
            threshold=self.threshold, 
            extract_segments=False
        )
        
        # Tri des détections pour l'affichage simulé
        detections_by_start = {s['start']: s for s in raw_segments}
        
        # On simule l'audio seconde par seconde (juste pour l'affichage)
        duration = librosa.get_duration(path=audio_path)
        detections = []
        
        for t in range(int(duration)):
            if t % 10 == 0: # Log toutes les 10 secondes audio pour pas saturer
                print(f"[AUDIO SIM] {t}s / {int(duration)}s...")
            
            # Si une chronique commence à cette seconde
            # On vérifie les détections qui tombent dans cette seconde
            for start_time in detections_by_start:
                if t <= start_time < t + 1:
                    s = detections_by_start[start_time]
                    print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE (AUDIO ML) : CHRONIQUE")
                    print(f">>> Début : {s['start']}s, Confiance : {s['conf']:.2f}\n")
                    
                    detections.append({
                        "label": "chronique",
                        "start": s['start'],
                        "end": s['end'],
                        "detected_at": s['end'],
                        "confidence": s['conf']
                    })
            
        return detections
