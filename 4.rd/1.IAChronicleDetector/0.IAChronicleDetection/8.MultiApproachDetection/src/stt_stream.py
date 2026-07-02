import mlx_whisper
from loguru import logger
import numpy as np

class STTStream:
    def __init__(self, model_name="mlx-community/whisper-base-mlx", language="fr"):
        logger.info(f"Loading MLX Whisper model: {model_name}")
        self.model_name = model_name
        self.language = language
        self.context_buffer = [] # Store recent segments
        
    def transcribe(self, audio_chunk):
        """
        Transcribe an audio chunk (numpy array).
        Returns a dict with 'text' and 'segments'.
        """
        try:
            # mlx_whisper.transcribe expects a path or a numpy array (16kHz)
            result = mlx_whisper.transcribe(
                audio_chunk,
                path_or_hf_repo=self.model_name,
                language=self.language,
                fp16=True # Good for M1
            )
            
            text = result.get("text", "").strip()
            if text:
                logger.debug(f"STT: {text}")
                self.context_buffer.append(text)
                if len(self.context_buffer) > 10:
                    self.context_buffer.pop(0)
                    
            return result
        except Exception as e:
            logger.error(f"STT Error: {e}")
            return {"text": "", "segments": []}

    def get_full_context(self):
        return " ".join(self.context_buffer)
