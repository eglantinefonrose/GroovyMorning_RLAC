import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/8.MultiApproachDetection"))
sys.path.append(METHOD_DIR)

try:
    from detect import FilePipeline
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(METHOD_DIR, "config/default.yaml")

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation pour Multi-Approach Pipeline.
        """
        if not os.path.exists(self.config_path):
            print(f"Error: Config not found at {self.config_path}")
            return []

        pipeline = FilePipeline(self.config_path, audio_path)
        # La méthode run_on_file renvoie déjà des détections au format presque standard
        raw_detections = pipeline.run_on_file(acceleration=0) # 0 pour batch
        
        detections = []
        for d in raw_detections:
            detections.append({
                "label": d.get("chronique", "chronique"),
                "start": d["start"],
                "end": d.get("end", d["start"] + 60.0),
                "detected_at": d["start"],
                "confidence": d.get("confidence", 1.0)
            })
            
        return detections
