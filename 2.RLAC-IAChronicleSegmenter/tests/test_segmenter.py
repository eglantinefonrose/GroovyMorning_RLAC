import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import os
import sys

# Ajouter le chemin pour importer UnifiedLiveSegmenter
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from live_radio_segmenter import UnifiedLiveSegmenter

class TestSegmenter(unittest.TestCase):
    @patch('whisper.load_model')
    @patch('live_radio_segmenter.UnifiedLiveSegmenter.load_jingles')
    def setUp(self, mock_load_jingles, mock_whisper):
        # Mock load_jingles to avoid loading real files
        self.segmenter = UnifiedLiveSegmenter(jingles_dir='/tmp/fake_jingles')
        self.segmenter.model = MagicMock()
        
        # Mock a jingle data
        self.mock_jingle = np.random.rand(16000).astype(np.float32) # 1 second of random noise
        self.segmenter.jingle_data = {
            "grande_matinale_jingle_7h.m4a": {
                "signal": self.mock_jingle,
                "length": len(self.mock_jingle),
                "norm": np.linalg.norm(self.mock_jingle)
            }
        }

    def test_normalize_text(self):
        self.assertEqual(self.segmenter.normalize_text("Bonjour Été"), "bonjour ete")

    @patch('requests.post')
    def test_jingle_detection(self, mock_post):
        # Create a "flux" containing the jingle
        flux = np.zeros(32000, dtype=np.float32) # 2 seconds of silence
        flux[8000:8000+len(self.mock_jingle)] = self.mock_jingle # Put jingle at 0.5s
        
        # Process in chunks
        chunk_size = self.segmenter.chunk_size
        for i in range(0, len(flux), chunk_size):
            chunk = flux[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            self.segmenter.process_audio_chunk(chunk)
            
            if self.segmenter.current_step > 0:
                break
        
        # Check if detected
        self.assertGreater(self.segmenter.current_step, 0)
        self.assertEqual(self.segmenter.last_chronicle_name, "journal de 7h")
        # Check if API was called
        self.assertTrue(mock_post.called)

if __name__ == '__main__':
    unittest.main()
