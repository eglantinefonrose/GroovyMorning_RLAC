import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/5.MachineLearningAudio-PretrainedModel"))
sys.path.append(METHOD_DIR)
sys.path.append(os.path.join(METHOD_DIR, 'src'))

try:
    from predict import predict as predict_internal
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_type="ast", threshold=0.4):
        self.model_type = model_type
        self.threshold = threshold
        
        # Détermination du répertoire du modèle par défaut
        if self.model_type == "ast":
            self.model_dir = os.path.join(METHOD_DIR, "model_output_ast")
        elif self.model_type == "beats":
            self.model_dir = os.path.join(METHOD_DIR, "model_output_beats")
        elif self.model_type == "wav2vec2":
            self.model_dir = os.path.join(METHOD_DIR, "model_output_facebook-wav2vec2-large-xlsr-53-french")

    def hms_to_seconds(self, hms):
        parts = hms.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard pour le framework d'évaluation.
        """
        if not os.path.exists(self.model_dir):
            print(f"Warning: Model directory not found at {self.model_dir}. Prediction might fail.")

        results_formatted = predict_internal(
            audio_path=audio_path,
            model_type=self.model_type,
            model_dir=self.model_dir,
            threshold=self.threshold
        )
        
        detections = []
        for res in results_formatted:
            start_sec = self.hms_to_seconds(res["start"])
            end_sec = self.hms_to_seconds(res["end"])
            detections.append({
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "label": "chronique",
                "detected_at": end_sec, # Supposé détecté à la fin de la fenêtre
                "confidence": res["confidence"]
            })
            
        return detections
