from .audio_capture import AudioStreamer
from .stt_stream import STTStream
from .audio_events import AudioEventDetector
from .acoustic_novelty import AcousticNoveltyDetector
from .diarization import DiarizationDetector
from .semantic_analysis import SemanticAnalyzer
from .fusion import FusionEngine
from .fingerprint_store import FingerprintStore
import yaml
from loguru import logger
import time

class ChroniclePipeline:
    def __init__(self, config_path, source):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        self.source = source
        self.streamer = AudioStreamer(
            source=source,
            sample_rate=self.config['audio']['sample_rate'],
            chunk_duration=self.config['audio']['chunk_duration']
        )
        
        self.stt = STTStream(
            model_name=self.config['stt']['model'],
            language=self.config['stt']['language']
        )
        
        self.audio_events = AudioEventDetector(sample_rate=self.config['audio']['sample_rate'])
        self.novelty = AcousticNoveltyDetector(sample_rate=self.config['audio']['sample_rate'])
        self.diarization = DiarizationDetector()
        
        self.semantic = SemanticAnalyzer(
            model=self.config['semantic']['ollama_model'],
            prompt_template_path=self.config['semantic']['prompt_path']
        )
        
        self.fusion = FusionEngine(thresholds=self.config['fusion']['thresholds'])
        self.store = FingerprintStore(db_path=self.config['fingerprint']['db_path'])

    def run(self):
        self.streamer.start()
        logger.info("Pipeline running. Press Ctrl+C to stop.")
        
        current_offset = 0.0
        chunk_duration = self.config['audio']['chunk_duration']
        
        try:
            for chunk in self.streamer.get_chunks():
                start_time = time.time()
                
                mins = int(current_offset // 60)
                secs = int(current_offset % 60)
                timestamp = f"[{mins:02d}:{secs:02d}] "
                
                # 1. Fingerprint check (Fast path)
                fp = self.store.generate_fingerprint(chunk)
                if fp:
                    match = self.store.find_match(self.source, fp)
                    if match:
                        logger.success(f"{timestamp}Fast Match: {match}")
                        current_offset += chunk_duration
                        continue
                
                # 2. Parallel Sensors (simplified here as sequential but could be multi-threaded)
                stt_result = self.stt.transcribe(chunk)
                music_score = self.audio_events.analyze(chunk)
                novelty_score = self.novelty.compute_novelty(chunk)
                speaker_distance = self.diarization.detect_change(chunk)
                
                # 3. Semantic Analysis (uses context)
                context = self.stt.get_full_context()
                semantic_result = self.semantic.analyze(context)
                
                # 4. Fusion
                scores = {
                    "novelty": novelty_score,
                    "music": music_score,
                    "speaker": speaker_distance,
                    "semantic": semantic_result.get("confidence", 0.0)
                }
                
                decision = self.fusion.fuse(scores, offset=current_offset)
                
                # 5. Learning
                if decision["is_detected"] and fp:
                    self.store.store_fingerprint(self.source, fp, 5.0, f"jingle_{int(time.time())}")
                
                elapsed = time.time() - start_time
                logger.debug(f"Chunk processed in {elapsed:.2f}s")
                current_offset += chunk_duration
                
        except KeyboardInterrupt:
            logger.info("Stopping pipeline...")
        finally:
            self.streamer.stop()
