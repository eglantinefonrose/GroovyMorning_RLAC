# Stage 1: Build
FROM gradle:8.12-jdk21-alpine AS build
WORKDIR /app
COPY . .
RUN ./gradlew installDist --no-daemon -x test
# Rename the distribution folder to a predictable name
RUN mv build/install/$(ls build/install | head -n 1) build/install/app-dist

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Install runtime dependencies (ffmpeg and curl)
RUN apk add --no-cache ffmpeg curl

# Create data and media directories for persistence
RUN mkdir -p data media

# Copy the built distribution
COPY --from=build /app/build/install/app-dist/ .

# Set environment variables
ENV SERVER_PORT=8000
ENV SERVER_HOST=0.0.0.0
ENV FFMPEG_PATH=ffmpeg
ENV DB_PATH=data/rlac.db

# Expose the application port
EXPOSE 8000

# Start the application using the generated script in bin/
# The script name usually matches the project name.
# We find it automatically, excluding .bat files.
ENTRYPOINT ["sh", "-c", "bin/$(ls bin | grep -v '\\.bat' | head -n 1)"]
