# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    ffmpeg \
    procps \
    libpq-dev \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY requirements.txt ./

# Install dependencies using uv
RUN uv pip install --system -r requirements.txt

# Pre-download Whisper model (medium) to avoid downloading at runtime
RUN python3 -c "import whisper; whisper.load_model('medium')"

# Copy the rest of the application code
COPY . .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Expose the port the API server runs on
EXPOSE 8001

# Run the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
