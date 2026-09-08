# Technical Specification: RLAC-IAChronicleSegmenter

## 1. Project Overview
The **RLAC-IAChronicleSegmenter** is a real-time system designed to detect, segment, and report the start and end of radio chronicles from the France Inter live stream. It employs a hybrid approach using acoustic jingle correlation, keyword matching, and advanced semantic analysis via Large Language Models (DeepSeek).

## 2. System Architecture
The system follows a modular architecture:
- **Audio Ingestion**: Captures live radio streams or simulated audio via FFmpeg and named pipes (FIFO).
- **Transcription Engine**: Converts audio to text in real-time using Whisper or Kyutai STT.
- **Detection Logic**: 
    - **Legacy Mode**: Acoustic correlation for jingles + keyword spotting.
    - **DeepSeek Mode**: Semantic analysis of transcripts validated against a scraped daily schedule.
- **Scraper**: Dynamically fetches the France Inter program grid via RPC calls.
- **API Server**: Manages scheduling, event persistence (SQLite), and real-time notifications (SocketIO).
- **External Integration**: Forwards events to a secondary Java-based backend.

---

## 3. Core Components

### 3.1. Audio Ingestion (`src/live_radio_segmenter.py`)
- **Input Formats**: 16kHz, Mono, Signed 16-bit Little Endian (s16le).
- **Sources**:
    - **Live**: `ffmpeg` capturing `https://stream.radiofrance.fr/franceinter/franceinter_hifi.m3u8`.
    - **Simulation**: Reads from a named pipe at `/tmp/audio_pipe`.
- **Buffering**: Maintains a circular buffer (default 60s) for recent audio and a secondary downsampled buffer (4kHz) for synchronization.

### 3.2. Transcription Wrapper (`src/transcriber.py`)
Provides a unified interface for multiple STT backends:
- **Whisper**: Supports `openai-whisper` and `faster-whisper`.
- **Kyutai STT**: Supports Rust-based binary, MLX (Mac Silicon), and Transformers (`stt-1b-en_fr`).
- **Streaming**: Implements a generator-based streaming transcription for low latency.

### 3.3. Semantic Detector (`src/deepseek_detector.py`)
- **Logic**: Uses DeepSeek API (`deepseek-chat`) to distinguish between *announcements* (future) and *actual starts* (present).
- **Validation**: 
    - Rejects detections occurring more than 5 minutes before scheduled time.
    - Ensures chronological order of chronicles.
    - Prevents duplicate detections for the same segment.

### 3.4. Radio Scraper (`src/scraper.py`)
- **Method**: Interrogates France Inter's internal RPC API (`loadProgramGrid` and `loadChroniclesGrid`).
- **Dynamic Hash Discovery**: Automatically finds the current RPC hash from the website.
- **Fallback**: Includes hardcoded UUIDs for the Matinale programs in case of discovery failure.

### 3.5. API Server & Scheduler (`api-server.py`)
- **Framework**: Flask + Flask-SocketIO.
- **Scheduler**: Uses the `schedule` library to manage start/stop times for the segmenter process.
- **Persistence**: SQLite database (`data/master_events.db`) with `master_chronicle_events` table.
- **Endpoints**:
    - `POST /api/realChronicleStartTime`: Logs start event, emits WebSocket, forwards to Java.
    - `POST /api/realChronicleEndTime`: Logs end event, emits WebSocket, forwards to Java.
    - `GET /api/chronicles`: Returns the scraped schedule for a given date.

---

## 4. Detection Logic Details

### 4.1. Legacy Mode (Acoustic)
- **Correlation**: Normalized cross-correlation between the live buffer and pre-loaded jingle templates (m4a converted to float32).
- **Thresholding**: Typically 0.50.
- **Keyword Spotting**: Simple string matching on normalized transcribed text.

### 4.2. DeepSeek Mode (Semantic)
- **System Prompt**: Instructs the LLM to output a JSON object containing `raisonnement`, `detecte` (boolean), `chronique` (name), and `phrase` (trigger text).
- **Context**: Sends the last 5 transcribed phrases as context to help distinguish announcements from launches.

---

## 5. Data Schema (SQLite)
Table: `master_chronicle_events`
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `chronicle_name`: TEXT
- `event_type`: TEXT ('start' or 'end')
- `master_timestamp`: TEXT (seconds in flux or epoch)
- `confidence`: FLOAT

---

## 6. Configuration & Environment
Key variables in `.env`:
- `DEEPSEEK_API_KEY`: Required for semantic mode.
- `USE_KYUTAI`: `true` to prioritize Kyutai over Whisper.
- `DETECTION_MODE`: `legacy` or `deepseek`.
- `SIMU`: `true` for pipe mode.
- `START_TIME` / `END_TIME`: Scheduling (e.g., `07:00` / `10:00`).
- `JAVA_API_URL`: Destination for event forwarding.

---

## 7. Execution Workflow
1. **Startup**: `api-server.py` starts and initializes the scheduler.
2. **Scheduling**: At the designated `START_TIME`, the server spawns `src/live_radio_segmenter.py`.
3. **Ingestion**: Audio is streamed into circular buffers.
4. **Processing**:
    - Text is transcribed in a separate thread.
    - If `deepseek`, text is analyzed for chronicle starts.
    - If `legacy`, audio is correlated for jingles.
5. **Event Reporting**: When a start/end is detected, a POST request is sent back to the API server.
6. **Reporting**: The API server persists the event and broadcasts it via WebSocket and HTTP Forwarding.

---

## 8. Project Structure
```text
.
├── api-server.py          # API Server, Scheduler, Event Forwarder
├── scheduler.py           # (Optional) Standalone scheduler logic
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Project metadata
├── .env                   # Configuration variables
├── data/
│   └── master_events.db   # SQLite database
├── src/
│   ├── live_radio_segmenter.py # Core engine (Ingestion & Detection)
│   ├── transcriber.py          # STT abstraction layer
│   ├── deepseek_detector.py    # LLM-based detection logic
│   ├── scraper.py              # Radio schedule scraper
│   └── ...
├── assets/
│   └── jingles_chroniques/     # Jingle templates for legacy mode
└── ...
```
