import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/6.LiveTranscriptionStartAndEndDetection"))
sys.path.append(METHOD_DIR)

try:
    from detect import transcribe_audio
    from inference_live_sim import LiveChronicleDetector
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_path=None, threshold=0.8):
        self.model_path = model_path or os.path.join(METHOD_DIR, "camembert_chronicle_start_v4")
        self.threshold = threshold

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation pour Live Transcription (Start/End detection).
        """
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at {self.model_path}")
            return []

        segments = transcribe_audio(audio_path)
        detector = LiveChronicleDetector(model_path=self.model_path, threshold=self.threshold)
        
        detections = []
        for seg in segments:
            # Affichage de la phrase en cours
            print(f"[{seg['start']:>7.2f}s] {seg['text']}")
            
            res = detector.process_new_sentence(seg['text'])
            if res:
                label = res.get("label", "chronique")
                print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE (CAMEMBERT LIVE) : {label.upper()}\n")
                
                detections.append({
                    "label": label,
                    "start": seg['start'],
                    "end": seg.get("end", seg['start'] + 60.0),
                    "detected_at": seg['start'],
                    "confidence": self.threshold
                })
                
        return detections
