import sqlite3
import acoustid
import numpy as np
import os
from loguru import logger

class FingerprintStore:
    def __init__(self, db_path="models/fingerprints.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fingerprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                radio_id TEXT,
                fingerprint TEXT,
                duration REAL,
                label TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def generate_fingerprint(self, audio_chunk, sample_rate=16000):
        """
        Generate fingerprint for an audio chunk.
        Note: acoustid.fingerprint expects raw PCM bytes.
        """
        try:
            # Convert float32 back to int16 for chromaprint
            pcm_data = (audio_chunk * 32768).astype(np.int16).tobytes()
            fp = acoustid.fingerprint(sample_rate, 1, iter([pcm_data]))
            return fp
        except Exception as e:
            logger.error(f"Fingerprint Error: {e}")
            return None

    def store_fingerprint(self, radio_id, fp, duration, label):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO fingerprints (radio_id, fingerprint, duration, label) VALUES (?, ?, ?, ?)',
            (radio_id, fp, duration, label)
        )
        conn.commit()
        conn.close()
        logger.info(f"Stored new fingerprint for {radio_id}: {label}")

    def find_match(self, radio_id, fp):
        """
        In a real scenario, we'd use acoustid's matching or chromaprint bitwise comparison.
        Here we do a simple exact or partial match for demo.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Very naive matching for demonstration
        cursor.execute('SELECT label FROM fingerprints WHERE radio_id = ? AND fingerprint = ?', (radio_id, fp))
        match = cursor.fetchone()
        conn.close()
        return match[0] if match else None
