import librosa
import numpy as np
from scipy.ndimage import gaussian_filter
from loguru import logger

class AcousticNoveltyDetector:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate

    def compute_novelty(self, audio_chunk):
        """
        Compute Foote novelty on a chunk.
        """
        if len(audio_chunk) < 2048:
            return 0.0
            
        # Compute Mel Spectrogram
        S = librosa.feature.melspectrogram(y=audio_chunk, sr=self.sample_rate, n_mels=128)
        S_db = librosa.power_to_db(S, ref=np.max)
        
        # Self-similarity matrix (SSM)
        # Using cosine similarity between columns of the spectrogram
        # For a short chunk, we just want to see if there's a big change in the middle
        
        # Recurrence matrix
        R = librosa.segment.recurrence_matrix(S_db, mode='affinity', sym=True)
        
        # Foote Novelty Kernel (checkered kernel)
        kernel_size = min(32, R.shape[0] // 2)
        if kernel_size < 4:
            return 0.0
            
        # Simplification: instead of full novelty curve on long audio, 
        # we check for "rupture" in this specific chunk
        # Calculate mean similarity between first and second half of the chunk
        half = R.shape[0] // 2
        block1 = R[:half, :half]
        block2 = R[half:, half:]
        cross = R[:half, half:]
        
        # Novelty score: internal similarity vs cross similarity
        internal = (np.mean(block1) + np.mean(block2)) / 2
        external = np.mean(cross)
        
        novelty_score = np.clip(internal - external, 0, 1)
        
        logger.debug(f"Acoustic Novelty: {novelty_score:.2f}")
        return float(novelty_score)
