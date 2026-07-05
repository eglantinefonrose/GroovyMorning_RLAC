import os
import sys
import json

# Configuration des chemins
METHOD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/9.ClaudeChronicleDetector"))
DEEPSEEK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../0.IAChronicleDetection/10.DeepSeekChronicleDetector"))
sys.path.append(METHOD_DIR)
sys.path.append(DEEPSEEK_DIR)

try:
    from detect import transcribe_audio, analyze_with_claude
except ImportError as e:
    print(f"Warning: Could not import detection modules from {METHOD_DIR}: {e}")

class Wrapper:
    def __init__(self):
        pass

    def process_stream(self, audio_path, buffer_size_seconds=None):
        """
        Implémentation pour Claude.
        """
        print(f"[WHISPER] Transcription de {audio_path} en cours...")
        
        try:
            from transcriber import Transcriber
            ts = Transcriber()
            segments_gen = ts.transcribe_stream(audio_path)
        except:
            print("[INFO] Utilisation de la transcription standard (bloquante)...")
            segments_gen = transcribe_audio(audio_path)
        
        history = []
        detections = []
        
        for seg in segments_gen:
            # Affichage de la phrase en cours
            print(f"[{seg['start']:>7.2f}s] {seg['text']}")
            
            res_raw = analyze_with_claude(seg['text'], history)
            try:
                res = json.loads(res_raw)
                if res.get("detecte"):
                    label = res.get("chronique", "chronique")
                    print(f"\n>>> 🔔 CHRONIQUE DÉTECTÉE (CLAUDE) : {label.upper()}")
                    
                    detections.append({
                        "label": label,
                        "start": seg['start'],
                        "end": seg['start'] + 60.0, # Durée par défaut comme dans l'original
                        "detected_at": seg['start'],
                        "confidence": 1.0
                    })
                history.append({"role": "user", "content": f"Phrase: \"{seg['text']}\""})
                history.append({"role": "assistant", "content": res_raw})
            except:
                pass
                
        return detections
