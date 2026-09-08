# Project Specification: RLAC-AudioRecorder (Java Backend)

This document provides a comprehensive technical specification for the RLAC-AudioRecorder project, designed to allow an AI agent to reconstruct the project from scratch while maintaining the exact architecture, functionalities, and conventions.

---

## 1. Project Overview
**RLAC-AudioRecorder** is a Java-based backend system responsible for capturing, scheduling, and segmenting radio audio streams. It operates as part of a larger ecosystem, interacting with a Python-based segmenter and providing a REST API for management.

### Key Capabilities:
- **Continuous Stream Capture**: Uses FFmpeg to maintain a circular buffer of 1-second HLS segments.
- **Dynamic Segmentation**: Reacts to real-time START/END notifications to extract specific audio "chronicles" from the continuous flow.
- **Master Synchronization**: Syncs its internal clock with a master source (Python segmenter) using audio fingerprinting and offset calculation.
- **Persistence**: Manages user configurations and chronicle schedules in a SQLite database.
- **HLS Serving**: Serves recorded segments and playlists via an embedded Jetty server.

---

## 2. Tech Stack & Environment
- **Runtime**: Java 21 (Amazon Corretto)
- **Build Tool**: Gradle 8.x
- **Web Server**: Embedded Eclipse Jetty 11
- **REST Framework**: Jersey 3.1 (JAX-RS)
- **Scheduling**: Quartz Scheduler 2.3 & Java `ScheduledExecutorService`
- **Database**: SQLite 3.45 with JDBC
- **Media Processing**: FFmpeg (must be installed on the host/container)
- **Networking**: Jersey Client, Socket.IO Client 2.1.0 (for WS integration)
- **Logging**: SLF4J with Logback

---

## 3. Core Architecture & Components

### 3.1 Package Structure
- `org.example.api`: REST API endpoints and Jetty server initialization.
- `org.example.api.dto`: Data Transfer Objects for API requests/responses.
- `recording.service`: Core domain logic for recording, scheduling, and FFmpeg management.
- `service`: Shared infrastructure services (Database, WebSocket, Business Logic).

### 3.2 Key Services (Singletons)

#### `FFmpegService`
- **Purpose**: Low-level FFmpeg process management.
- **Continuous Recording**: Captures `franceinter-hifi.aac` (or configured URL) into `media/continuous/` as 1s `.m4s` segments.
- **Master Sync**: Generates a 2s audio fingerprint (`s16le`, 4000Hz, mono) and sends it to the Python API to calculate a `masterOffsetSeconds`.
- **Chronicle Recording**: Uses file-system hard links (`Files.createLink`) to "copy" segments from the continuous flow into chronicle-specific folders without duplicating data on disk.
- **Manifest Generation**: Dynamically creates and updates `.m3u8` playlists for each chronicle.

#### `DynamicRecordingService`
- **Purpose**: Stateful management of active recording sessions.
- **Session Tracking**: Maintains a map of `RecordingSession` objects.
- **Start/End Handling**:
    - `handleStartNotification`: Triggers the `FFmpegService` to start tracking segments for a specific chronicle.
    - `handleEndNotification`: Triggers the finalization and truncation of the chronicle's segments.
- **Daily Cleanup**: Clears `media/continuous` daily at 06:55 (5 minutes before the reference hour 07:00).

#### `ChroniclesManagerService`
- **Purpose**: Manages the list of authorized chronicles for each user.
- **Persistence**: Bridges the logic between the API and `DatabaseService`.
- **Sync**: Can synchronize the local chronicle list with an external radio grid API.

#### `DatabaseService`
- **Purpose**: DAO for SQLite.
- **Schema**:
    - `app_config`: Key-value pairs (e.g., `local_user_id`).
    - `users`: User-specific config (`user_id`, `username`).
    - `user_chronicles`: Scheduled chronicles (`id`, `user_id`, `chronicle_name`, `start_time`, `end_time`, `play_order`).
    - `user_status`: Tracks if a user has a customized chronicle list.

#### `RLACServerAPI`
- **Purpose**: Entry point and REST controller.
- **Embedded Jetty**: Configures `ResourceHandler` to serve the `media/` directory as static files and `ServletContainer` for Jersey API.

---

## 4. API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/status` | Health check and server status. |
| `GET` | `/api/findTodayFolder` | Returns the session folder path for the current day. |
| `POST` | `/api/addChronicle` | Adds a new chronicle to the user's schedule. |
| `GET` | `/api/getUserChronicles` | Lists all chronicles for the user (triggering sync). |
| `DELETE` | `/api/removeChronicles` | Deletes all chronicles for the user. |
| `DELETE` | `/api/clearUserConfig` | Resets user configuration to defaults. |
| `POST` | `/api/realChronicleStartTime` | **Critical**: Notifies the system that a chronicle has started. |
| `POST` | `/api/realChronicleEndTime` | **Critical**: Notifies the system that a chronicle has ended. |
| `POST` | `/api/ping` | Ensures the continuous flow is running. |
| `POST` | `/api/feedAudio` | Extracts a 1s chunk at a specific position and sends it to Python. |

---

## 5. Workflows & Logic

### 5.1 The "Continuous-to-Chronicle" Workflow
1. **Startup**: `FFmpegService` starts a background process capturing the radio stream into `media/continuous/continuous_segment_%05d.m4s`.
2. **Notification**: Python Segmenter detects a chronicle start via AI/Signal and calls `POST /api/realChronicleStartTime?nomDeChronique=X`.
3. **Tracking**: `DynamicRecordingService` creates a `RecordingSession`. `FFmpegService` starts a `ChronicleRecordingTask` thread.
4. **Linking**: The task thread monitors `media/continuous/continuous.m3u8`. For every new segment appearing that falls within the chronicle's time window, it creates a hard link in `media/userID_[id]/session_[date]_dynamic/X/`.
5. **Completion**: Python calls `POST /api/realChronicleEndTime?nomDeChronique=X&realDuration=Y`.
6. **Finalization**: `FFmpegService` truncates segments exceeding the real duration, adds `#EXT-X-ENDLIST` to the chronicle's `.m3u8`, and cleans up.

### 5.2 Synchronization Logic
The system uses an "Initial Sync" pattern:
1. Wait for segment 5 of the continuous flow.
2. Extract 2s of audio.
3. Send to Python API `/api/sync_offset`.
4. Python returns a `delta` (time difference) and `score` (confidence).
5. Java updates `masterOffsetSeconds`, which is then applied to all `absoluteStartTime` calculations to ensure perfect alignment with the Python segmenter's view of time.

### 5.3 Notification Mechanisms
The system supports two ways of receiving START/END notifications from the Python segmenter:
1. **REST API**: Standard `POST` requests to `/api/realChronicleStartTime` and `/api/realChronicleEndTime`.
2. **WebSockets**: `WebSocketClientService` connects to the Python API via Socket.IO and listens for `chronicle_start` and `chronicle_end` events. This allows for low-latency, real-time triggers.

---

## 6. Deployment & Configuration

### Environment Variables
- `SERVER_PORT`: Default `8000`.
- `SERVER_HOST`: Default `0.0.0.0`.
- `DB_PATH`: Path to SQLite DB (default `data/rlac.db`).
- `PYTHON_API_URL`: URL of the Python segmenter (default `http://localhost:8001`).
- `FFMPEG_PATH`: Path to FFmpeg executable (default `ffmpeg`).
- `DISABLE_MASTER_SYNC`: If `true`, skips the fingerprint sync.

### Dockerization
- **Base Image**: `amazoncorretto:21-alpine`.
- **Requirements**: `ffmpeg` and `curl` must be installed in the container.
- **Volumes**:
    - `/app/data`: For the SQLite database.
    - `/app/media`: For recording storage.

### Build System
- `gradle run`: Runs the application.
- `gradle buildDockerImage`: Builds the local Docker image.
- `gradle deployOnLinuxServer`: Orchestrates remote deployment via SSH and Docker Compose.

---

## 7. Storage Structure
```text
media/
├── continuous/              # Circular buffer (fmp4 segments)
│   ├── continuous.m3u8
│   ├── continuous_init.mp4
│   └── continuous_segment_00000.m4s
└── userID_[ID]/
    └── session_[YYYYMMDD]_dynamic/
        └── [ChronicleName]/
            ├── [ChronicleName].m3u8
            ├── [ChronicleName]_init.mp4
            └── [ChronicleName]_segment_00000.m4s
```

---

## 8. Development Notes
- **Thread Safety**: Core services must handle concurrent API calls and background FFmpeg tasks. Use `ConcurrentHashMap` and `synchronized` blocks where appropriate.
- **Idempotency**: START/END notifications should be handled gracefully if repeated or received out of order.
- **Resource Management**: Always ensure FFmpeg processes are destroyed on shutdown via Shutdown Hooks.
