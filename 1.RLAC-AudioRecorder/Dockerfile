# Use an official OpenJDK runtime as a parent image
FROM amazoncorretto:21-alpine

# Set the working directory in the container
WORKDIR /app

# Create data directory for SQLite
RUN mkdir -p /app/data

# Copy the fat jar into the container at /app
COPY build/libs/1.RLAC-JavaServer-1.0-SNAPSHOT.jar /app/application.jar

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the jar file
ENTRYPOINT ["java", "-jar", "application.jar"]
