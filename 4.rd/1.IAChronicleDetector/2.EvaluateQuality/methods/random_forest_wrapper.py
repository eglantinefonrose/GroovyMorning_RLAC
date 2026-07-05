import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/2.MachineLearningTranscription-RandomForest"))
sys.path.append(METHOD_DIR)

try:
    from predict import predict_chroniques
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self, model_path=None, threshold=0.4):
        self.model_path = model_path or os.path.join(METHOD_DIR, "models/radio_chronique_rf.pkl")
        self.threshold = threshold

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation de l'interface standard.
        Note: Cette approche utilise un fichier SRT déjà généré ou doit en générer un.
        Pour ce wrapper, on va supposer qu'on peut lui passer un chemin SRT ou qu'il le déduit.
        """
        # Dans ce projet, le SRT est souvent à côté de l'audio ou passé explicitement.
        # Pour simplifier dans le cadre de l'évaluateur, on va chercher un SRT correspondant.
        srt_path = audio_path.replace(".mp3", ".srt").replace(".wav", ".srt")
        
        # Si le SRT n'existe pas, on ne peut pas faire grand chose sans Whisper ici.
        # Dans une version complète, on appellerait Whisper.
        if not os.path.exists(srt_path):
            print(f"Warning: SRT file not found at {srt_path}. Random Forest needs transcription.")
            return []

        if not os.path.exists(self.model_path):
            print(f"Error: Model not found at {self.model_path}")
            return []

        raw_chroniques, _ = predict_chroniques(
            self.model_path, 
            srt_path, 
            confidence_threshold=self.threshold
        )
        
        # Pour simuler le live, on charge le SRT pour afficher les phrases
        import sys
        # On peut réutiliser load_transcription si dispo ou parser manuellement
        # Ici on va juste afficher les détections au fur et à mesure du temps
        print("[INFO] Simulation du flux pour Random Forest...")
        
        detections = []
        # On trie les chroniques par début
        sorted_raw = sorted(raw_chroniques, key=lambda x: x[0])
        
        # On simule le passage du temps (très rapide)
        last_t = 0
        for start, end in sorted_raw:
            # On pourrait intercaler l'affichage des phrases ici si on lisait le SRT
            print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE (RANDOM FOREST) : CHRONIQUE")
            print(f">>> Intervalle : {start:.2f}s - {end:.2f}s\n")
            
            detections.append({
                "label": "chronique",
                "start": start,
                "end": end,
                "detected_at": end,
                "confidence": 1.0 
            })
            
        return detections
