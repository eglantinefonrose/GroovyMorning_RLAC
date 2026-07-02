import subprocess
import numpy as np
from loguru import logger
import threading
import queue

class AudioStreamer:
    def __init__(self, source, sample_rate=16000, chunk_duration=5.0):
        self.source = source
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration)
        self.queue = queue.Queue(maxsize=100)
        self.running = False
        self._process = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Started audio capture from {self.source}")

    def _run(self):
        cmd = [
            'ffmpeg',
            '-i', self.source,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ac', '1',
            '-ar', str(self.sample_rate),
            '-loglevel', 'quiet',
            '-'
        ]
        
        try:
            self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            while self.running:
                # Read chunk_size * 2 bytes (16-bit PCM = 2 bytes per sample)
                raw_data = self._process.stdout.read(self.chunk_size * 2)
                if not raw_data:
                    break
                
                audio_array = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                self.queue.put(audio_array)
                
        except Exception as e:
            logger.error(f"Error in audio capture: {e}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self._process:
            self._process.terminate()
        logger.info("Stopped audio capture")

    def get_chunks(self):
        while self.running or not self.queue.empty():
            try:
                yield self.queue.get(timeout=1.0)
            except queue.Empty:
                continue
