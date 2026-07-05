import os
import sys
import json
import torch

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/4.TransformerDetection"))
sys.path.append(METHOD_DIR)

try:
    from detect import transcribe_audio, predict_chroniques
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_path=None, threshold=0.5):
        self.model_path = model_path or os.path.join(METHOD_DIR, "models/camembert_chronicle")
        self.threshold = threshold

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard pour le framework d'évaluation.
        """
        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at {self.model_path}")
            return []

        # Pour TransformerDetection, on transcrit d'abord tout l'audio
        segments = transcribe_audio(audio_path)
        
        # Simulation live : on parcourt les segments et on affiche
        # même si la prédiction est techniquement faite en batch dans le wrapper original.
        # On va adapter pour simuler le comportement live.
        print("[INFO] Simulation du flux pour Transformer (Camembert)...")
        
        # On prédit les chroniques
        raw_detections = predict_chroniques(self.model_path, segments, threshold=self.threshold)
        
        # On crée un dictionnaire des détections par index de segment pour l'affichage "live"
        detections_by_start = {d["start"]: d for d in raw_detections}
        
        detections = []
        for seg in segments:
            print(f"[{seg['start']:>7.2f}s] {seg['text']}")
            
            if seg['start'] in detections_by_start:
                d = detections_by_start[seg['start']]
                label = d.get("label", "chronique")
                print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE (TRANSFORMER) : {label.upper()}\n")
                
                detections.append({
                    "label": label,
                    "start": d["start"],
                    "end": d["end"],
                    "detected_at": d["end"], 
                    "confidence": d.get("confidence", 1.0)
                })
            
        return detections
