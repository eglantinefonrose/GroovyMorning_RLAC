import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class TestProjectImports(unittest.TestCase):
    def test_imports(self):
        try:
            from src.audio_capture import AudioStreamer
            from src.stt_stream import STTStream
            from src.audio_events import AudioEventDetector
            from src.acoustic_novelty import AcousticNoveltyDetector
            from src.diarization import DiarizationDetector
            from src.semantic_analysis import SemanticAnalyzer
            from src.fusion import FusionEngine
            from src.fingerprint_store import FingerprintStore
            from src.pipeline import ChroniclePipeline
        except ImportError as e:
            self.fail(f"Import failed: {e}")

if __name__ == "__main__":
    unittest.main()
