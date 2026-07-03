from speechbrain.inference.speaker import EncoderClassifier
import torch
import numpy as np
from loguru import logger

class DiarizationDetector:
    def __init__(self, model_source="speechbrain/spkrec-ecapa-voxceleb"):
        logger.info(f"Loading Diarization model: {model_source}")
        self.classifier = EncoderClassifier.from_hparams(source=model_source)
        self.last_embedding = None
        
    def detect_change(self, audio_chunk):
        """
        Detect if speaker changed compared to last chunk.
        """
        # Convert to torch tensor
        signal = torch.from_numpy(audio_chunk).unsqueeze(0)
        
        # Get embeddings
        with torch.no_grad():
            embeddings = self.classifier.encode_batch(signal)
            embeddings = embeddings.squeeze(1).numpy()
            
        if self.last_embedding is None:
            self.last_embedding = embeddings
            return 0.0
            
        # Cosine similarity
        similarity = np.dot(self.last_embedding, embeddings.T) / (
            np.linalg.norm(self.last_embedding) * np.linalg.norm(embeddings)
        )
        
        # Distance = 1 - similarity
        distance = 1.0 - float(similarity.item())
        self.last_embedding = embeddings
        
        logger.debug(f"Speaker Distance: {distance:.2f}")
        return distance
