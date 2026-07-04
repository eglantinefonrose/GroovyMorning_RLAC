import argparse
import json
import sys
import os
from pathlib import Path
from loguru import logger

# Configuration de loguru pour être discret sur stderr
logger.remove()
logger.add(sys.stderr, level="INFO")

from src.pipeline import ChroniclePipeline

import time

class FilePipeline(ChroniclePipeline):
    def __init__(self, config_path, source):
        super().__init__(config_path, source)
        self.detections = []

    def run_on_file(self, acceleration=0.0):
        self.streamer.start()
        current_offset = 0.0
        chunk_duration = self.config['audio']['chunk_duration']
        
        t0 = time.time()
        try:
            for chunk in self.streamer.get_chunks():
                if acceleration > 0:
                    target_time = current_offset / acceleration
                    elapsed = time.time() - t0
                    sleep_time = target_time - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                # 1. Fingerprint check
                fp = self.store.generate_fingerprint(chunk)
                if fp:
                    match = self.store.find_match(self.source, fp)
                    if match:
                        self.detections.append({
                            "start": round(current_offset, 2),
                            "end": round(current_offset + chunk_duration, 2),
                            "label": f"Match: {match}",
                            "confidence": 1.0,
                            "method": "fingerprint"
                        })
                        current_offset += chunk_duration
                        continue
                
                # 2. Analysis
                stt_result = self.stt.transcribe(chunk)
                music_score = self.audio_events.analyze(chunk)
                novelty_score = self.novelty.compute_novelty(chunk)
                speaker_distance = self.diarization.detect_change(chunk)
                
                context = self.stt.get_full_context()
                semantic_result = self.semantic.analyze(context)
                
                scores = {
                    "novelty": novelty_score,
                    "music": music_score,
                    "speaker": speaker_distance,
                    "semantic": semantic_result.get("confidence", 0.0)
                }
                
                decision = self.fusion.fuse(scores, offset=current_offset)
                
                if decision["is_detected"]:
                    self.detections.append({
                        "start": round(current_offset, 2),
                        "end": round(current_offset + chunk_duration, 2),
                        "label": "chronique",
                        "confidence": round(decision["combined_score"], 3),
                        "method": "fusion"
                    })
                
                current_offset += chunk_duration
                
        except Exception as e:
            logger.error(f"Error during processing: {e}")
        finally:
            self.streamer.stop()
            
        return self.detections

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche Multi-Pipeline)")
    parser.add_argument("audio", help="Chemin audio")
    parser.add_argument("--config", default="config/default.yaml", help="Config YAML")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        sys.exit(1)
        
    pipeline = FilePipeline(args.config, args.audio)
    results = pipeline.run_on_file()
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
