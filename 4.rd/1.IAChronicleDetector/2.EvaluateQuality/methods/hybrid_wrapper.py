import os
import sys
import json
import torch
import numpy as np

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/3.MachineLearningTranscription-Hybrid"))
sys.path.append(METHOD_DIR)

try:
    from train import RadioChroniqueClassifier, HybridSequenceClassifier
    from utils import load_transcription
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, base_model=None, hybrid_model=None):
        self.base_model = base_model or os.path.join(METHOD_DIR, "models/radio_chronique_hybrid_base.pkl")
        self.hybrid_model = hybrid_model or os.path.join(METHOD_DIR, "models/radio_chronique_hybrid_hybrid.pt")

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard.
        Approche hybride : nécessite un SRT.
        """
        srt_path = audio_path.replace(".mp3", ".srt").replace(".wav", ".srt")
        if not os.path.exists(srt_path):
            print(f"Warning: SRT file not found at {srt_path}. Hybrid method needs transcription.")
            return []

        if not os.path.exists(self.base_model) or not os.path.exists(self.hybrid_model):
            print(f"Error: Models not found for Hybrid method.")
            return []

        segments = load_transcription(srt_path)
        
        # On utilise une version simplifiée de la simulation live du script evaluate_quality.py original
        base_extractor = RadioChroniqueClassifier.load_model(self.base_model)
        hybrid_clf = HybridSequenceClassifier.load(self.hybrid_model)
        hybrid_clf.device = torch.device('cpu')
        hybrid_clf.model.to(torch.device('cpu'))
        
        seq_len = hybrid_clf.seq_len
        all_preds = np.zeros(len(segments), dtype=int)
        all_probs = np.zeros(len(segments))
        
        hybrid_clf.model.eval()
        with torch.no_grad():
            for i in range(len(segments)):
                start_idx = max(0, i - seq_len + 1)
                window_segments = segments[start_idx:i+1]
                X_window = base_extractor.prepare_features(window_segments, training=False)
                
                if len(X_window) < seq_len:
                    padding = np.zeros((seq_len - len(X_window), X_window.shape[1]))
                    X_window = np.vstack([padding, X_window])
                    
                X_tensor = torch.FloatTensor(X_window).unsqueeze(0).to(hybrid_clf.device)
                preds = hybrid_clf.model.decode(X_tensor)[0]
                emissions = hybrid_clf.model.emissions(X_tensor)
                probs = torch.softmax(emissions, dim=2)[0, :, 1].cpu().numpy()
                
                all_preds[i] = preds[-1]
                all_probs[i] = probs[-1]

        detections = []
        current = None
        for i, label in enumerate(all_preds):
            if label > 0:
                if current is None:
                    current = {'start': segments[i]['start'], 'end': segments[i]['end'], 'conf': all_probs[i]}
                else:
                    current['end'] = segments[i]['end']
                    current['conf'] = max(current['conf'], all_probs[i])
            else:
                if current:
                    if current['end'] - current['start'] >= 5.0:
                        detections.append({
                            "label": "chronique",
                            "start": current['start'],
                            "end": current['end'],
                            "detected_at": current['end'],
                            "confidence": current['conf']
                        })
                    current = None
                    
        if current and current['end'] - current['start'] >= 5.0:
            detections.append({
                "label": "chronique",
                "start": current['start'],
                "end": current['end'],
                "detected_at": current['end'],
                "confidence": current['conf']
            })
            
        return detections
