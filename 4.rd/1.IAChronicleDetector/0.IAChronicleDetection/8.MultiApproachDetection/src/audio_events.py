import librosa
import numpy as np
from loguru import logger

class AudioEventDetector:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate

    def analyze(self, audio_chunk):
        """
        Detect if music is present in the chunk.
        Returns a score between 0 and 1.
        """
        if len(audio_chunk) < 1024:
            return 0.0
            
        # Simplified Music/Speech detection using Spectral Centroid and Zero Crossing Rate
        cent = librosa.feature.spectral_centroid(y=audio_chunk, sr=self.sample_rate)
        zcr = librosa.feature.zero_crossing_rate(audio_chunk)
        rms = librosa.feature.rms(y=audio_chunk)
        
        # Music typically has more stable energy and different spectral characteristics than speech
        # This is a heuristic. In a real system, we'd use YAMNet/PANNs.
        mean_cent = np.mean(cent)
        std_cent = np.std(cent)
        mean_zcr = np.mean(zcr)
        
        # High RMS + high spectral variation often indicates music/jingle
        music_score = np.clip((std_cent / 1000.0) + (mean_zcr * 2.0), 0, 1)
        
        logger.debug(f"Audio Event - Music Score: {music_score:.2f}")
        return music_score
