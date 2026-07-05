from faster_whisper import WhisperModel
import os

class Transcriber:
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        """
        Initialise le modèle Faster-Whisper.
        'base' est un bon compromis vitesse/précision.
        """
        print(f"[WHISPER] Chargement du modèle '{model_size}' sur {device} ({compute_type})...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_stream(self, audio_path):
        """
        Générateur qui transcrit le fichier audio et renvoie les segments.
        Chaque segment contient : start, end, text.
        """
        print(f"[WHISPER] Début de la transcription : {audio_path}")
        segments, info = self.model.transcribe(audio_path, beam_size=5, language="fr")
        
        for segment in segments:
            yield {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }
