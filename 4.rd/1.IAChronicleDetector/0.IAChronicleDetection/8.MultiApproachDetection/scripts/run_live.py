import argparse
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline import ChroniclePipeline
from loguru import logger

def main():
    parser = argparse.ArgumentParser(description="Radio Chronicle Detector - Multi-Approach")
    parser.add_argument("--source", type=str, required=True, help="URL of radio stream or path to local audio file")
    parser.add_argument("--config", type=str, default="config/default.yaml", help="Path to config file")
    parser.add_argument("--output", type=str, help="Path to output JSON file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if not args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    
    logger.info(f"Starting detection on source: {args.source}")
    
    pipeline = ChroniclePipeline(args.config, args.source)
    detections = []
    
    try:
        for det in pipeline.run():
            detections.append(det)
            if args.output:
                # Optional: write incrementally or just keep in memory
                pass
    except KeyboardInterrupt:
        pass
    finally:
        if args.output:
            logger.info(f"Saving {len(detections)} detections to {args.output}")
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(detections, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
