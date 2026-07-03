# Radio Chronicle Detector (Multi-Approach)

A modular Python system to detect radio chronicle starts in real-time using audio features, transcription, and LLM analysis.

## Features
- **Capture**: Live radio stream (HLS/Icecast) or local file.
- **STT**: Apple Silicon optimized transcription using `mlx-whisper`.
- **Audio Analysis**: Music/Speech classification and acoustic novelty detection.
- **Diarization**: Speaker change detection using `SpeechBrain`.
- **Semantic Analysis**: LLM-based transition detection via `Ollama`.
- **Learning**: Acoustic fingerprinting to remember jingles.

## Installation
1. Install [ffmpeg](https://ffmpeg.org/).
2. Install [Ollama](https://ollama.com/) and pull the model:
   ```bash
   ollama pull llama3.2:3b
   ```
3. Setup environment:
   ```bash
   cd 8.MultiApproachDetection
   uv venv
   source .venv/bin/activate
   uv sync
   ```

## Usage
Run on a local file:
```bash
python scripts/run_live.py --source data/samples/test.mp3
```

Run on a live stream:
```bash
python scripts/run_live.py --source http://stream.radiofrance.fr/franceinter/franceinter_hifi.m3u8
```

## Architecture
- `src/audio_capture.py`: Manages audio ingestion.
- `src/stt_stream.py`: Handles continuous transcription.
- `src/audio_events.py`: Detects music/speech segments.
- `src/semantic_analysis.py`: LLM reasoning on transcripts.
- `src/fusion.py`: Multi-signal scoring and decision.
