# Build stage
FROM amazoncorretto:21-alpine AS builder

WORKDIR /app

# Copy gradle files
COPY gradlew .
COPY gradle gradle
COPY build.gradle .
COPY settings.gradle .

# Download dependencies (cache layer)
RUN ./gradlew --no-daemon dependencies

# Copy source code
COPY src src

# Build the application distribution
RUN ./gradlew --no-daemon installDist

# Runtime stage
FROM amazoncorretto:21-alpine

# Install runtime dependencies: FFmpeg, curl, and bash
# FFmpeg is required for recording and extraction
# Curl is required for sending audio chunks to the external API (localhost:8001)
RUN apk add --no-cache ffmpeg curl bash

WORKDIR /app

# Create data and media directories for persistence
RUN mkdir -p data media

# Copy the built distribution from the builder stage
# The application plugin creates the distribution in build/install/1.RLAC-AudioRecorder
COPY --from=builder /app/build/install/1.RLAC-AudioRecorder .

# Expose the API port
EXPOSE 8000

# Environment variables
# DB_PATH: Path to the SQLite database
# FFMPEG_PATH: Path to the ffmpeg executable
ENV DB_PATH=/app/data/rlac.db
ENV FFMPEG_PATH=/usr/bin/ffmpeg

# The application plugin creates a start script in bin/1.RLAC-AudioRecorder
# We use this as the entrypoint
ENTRYPOINT ["./bin/1.RLAC-AudioRecorder"]
