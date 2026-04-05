package recording.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;
import java.util.List;
import java.util.ArrayList;

public class FFmpegService {
    private static final Logger logger = LoggerFactory.getLogger(FFmpegService.class);
    private static final String AUDIO_PIPE_PATH = "/tmp/audio_pipe_java";
    private static final String FFMPEG_PATH = System.getenv().getOrDefault("FFMPEG_PATH", "ffmpeg");

    private final Map<String, ChronicleRecordingTask> activeChronicleTasks = new ConcurrentHashMap<>();
    private Process continuousProcess;
    private long continuousStartTime;

    public void startContinuousRecording() {
        if (continuousProcess != null && continuousProcess.isAlive()) {
            return;
        }

        File continuousDir = new File("media/continuous");
        if (!continuousDir.exists()) {
            continuousDir.mkdirs();
        }

        File playlistFile = new File(continuousDir, "continuous.m3u8");
        
        // Supprimer l'ancienne playlist et les segments pour repartir de zéro
        if (playlistFile.exists()) {
            playlistFile.delete();
            File[] files = continuousDir.listFiles((dir, name) -> name.startsWith("continuous_"));
            if (files != null) {
                for (File f : files) f.delete();
            }
        }

        ProcessBuilder pb = new ProcessBuilder(
                FFMPEG_PATH,
                "-f", "s16le",
                "-ar", "16000",
                "-ac", "1",
                "-i", AUDIO_PIPE_PATH,
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-f", "hls",
                "-hls_time", "1",
                "-hls_list_size", "0",
                "-hls_segment_type", "fmp4",
                "-hls_fmp4_init_filename", "continuous_init.mp4",
                "-hls_segment_filename", "continuous_segment_%05d.m4s",
                playlistFile.getAbsolutePath()
        );

        pb.directory(continuousDir);
        pb.redirectErrorStream(true);

        try {
            logger.info("🎬 Starting continuous FFmpeg recording (1s segments) in media/continuous/");
            continuousStartTime = System.currentTimeMillis();
            continuousProcess = pb.start();

            // Shutdown hook pour FFmpeg
            Runtime.getRuntime().addShutdownHook(new Thread(this::stopContinuousRecording));

            // Démarrer l'extraction automatique du chunk de 2s à 3s
            startAutomaticChunkExtraction();

            new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(continuousProcess.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        logger.debug("ffmpeg (continuous): {}", line);
                    }
                } catch (Exception e) {
                    logger.error("Error reading continuous ffmpeg output", e);
                } finally {
                    logger.info("🏁 Continuous FFmpeg process finished");
                }
            }).start();

        } catch (Exception e) {
            logger.error("Failed to start continuous FFmpeg", e);
        }
    }

    public void stopContinuousRecording() {
        if (continuousProcess != null && continuousProcess.isAlive()) {
            logger.info("Stopping continuous recording");
            continuousProcess.destroy();
            continuousProcess = null;
        }
    }

    private void startAutomaticChunkExtraction() {
        new Thread(() -> {
            // Le segment 00002.m4s correspond à l'intervalle [2s, 3s] (00000=[0,1], 00001=[1,2])
            File segmentFile = new File("media/continuous/continuous_segment_00002.m4s");
            logger.info("⏳ Waiting for segment 00002 to extract automatic chunk...");
            
            // Attendre jusqu'à 30 secondes que le segment soit généré
            for (int i = 0; i < 30; i++) {
                if (segmentFile.exists() && segmentFile.length() > 0) {
                    break;
                }
                try { Thread.sleep(1000); } catch (InterruptedException e) { return; }
            }
            
            if (segmentFile.exists()) {
                logger.info("✅ Segment 00002 found, extracting and sending chunk...");
                extractAndSendFromSegment(segmentFile, 2);
            } else {
                logger.error("❌ Segment 00002 never appeared, automatic extraction failed.");
            }
        }).start();
    }

    private void extractAndSendFromSegment(File segmentFile, int positionInSeconds) {
        String chunkPath = "media/auto_chunk_" + System.currentTimeMillis() + ".raw";
        
        // Conversion du segment m4s (AAC) vers raw s16le (16kHz mono)
        ProcessBuilder extractPb = new ProcessBuilder(
                FFMPEG_PATH,
                "-i", segmentFile.getAbsolutePath(),
                "-f", "s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                chunkPath
        );

        try {
            Process extractProcess = extractPb.start();
            extractProcess.waitFor();

            if (new File(chunkPath).exists()) {
                // Envoi via curl
                ProcessBuilder sendPb = new ProcessBuilder(
                        "curl",
                        "-X", "POST",
                        "http://localhost:8001/api/feed_audio?positionInSeconds=" + positionInSeconds,
                        "--data-binary", "@" + chunkPath
                );
                
                logger.info("🚀 Automatically sending 1s chunk (2s-3s) to external API");
                Process sendProcess = sendPb.start();
                sendProcess.waitFor();
                
                // Nettoyage
                new File(chunkPath).delete();
            }
        } catch (Exception e) {
            logger.error("Error in extractAndSendFromSegment", e);
        }
    }

    public void extractAndSendChunk(int positionInSeconds) {
        String chunkPath = "media/chunk_" + System.currentTimeMillis() + ".raw";
        
        // Extraction de 1 seconde à partir de positionInSeconds
        ProcessBuilder extractPb = new ProcessBuilder(
                FFMPEG_PATH,
                "-f", "s16le",
                "-ar", "16000",
                "-ac", "1",
                "-i", AUDIO_PIPE_PATH,
                "-ss", String.valueOf(positionInSeconds),
                "-t", "1",
                "-f", "s16le",
                "-y",
                chunkPath
        );

        try {
            logger.info("Extracting 1s chunk from {} at {}s", AUDIO_PIPE_PATH, positionInSeconds);
            Process extractProcess = extractPb.start();
            extractProcess.waitFor();

            if (new File(chunkPath).exists()) {
                // Envoi via curl
                ProcessBuilder sendPb = new ProcessBuilder(
                        "curl",
                        "-X", "POST",
                        "http://localhost:8001/api/feed_audio?positionInSeconds=" + positionInSeconds,
                        "--data-binary", "@" + chunkPath
                );
                
                logger.info("Sending chunk to external API: {}", positionInSeconds);
                Process sendProcess = sendPb.start();
                sendProcess.waitFor();
                
                // Nettoyage
                new File(chunkPath).delete();
            } else {
                logger.error("Failed to create chunk file at {}", chunkPath);
            }
        } catch (Exception e) {
            logger.error("Error in extractAndSendChunk", e);
        }
    }

    public long getContinuousStartTime() {
        return continuousStartTime;
    }

    public void startRecording(String userId, String chronicleName, String folderName, long absoluteStartTimeMs) {
        String sessionKey = userId + ":" + chronicleName;
        if (activeChronicleTasks.containsKey(sessionKey)) {
            logger.warn("Recording task already in progress for {}", sessionKey);
            return;
        }

        String cleanChronicleName = chronicleName.replaceAll("[^a-zA-Z0-9]", "_");
        File baseSessionDir = new File("media/userID_" + userId, folderName);
        File chronicleRecordingDir = new File(baseSessionDir, cleanChronicleName);

        if (!chronicleRecordingDir.exists()) {
            chronicleRecordingDir.mkdirs();
        }

        // Copier le fichier init du master si possible, sinon attendre qu'il soit créé
        File initFile = new File("media/continuous/continuous_init.mp4");
        for (int i = 0; i < 15 && !initFile.exists(); i++) {
            try { Thread.sleep(1000); } catch (InterruptedException ignored) {}
        }
        
        try {
            if (initFile.exists()) {
                java.nio.file.Files.copy(
                    initFile.toPath(),
                    new File(chronicleRecordingDir, cleanChronicleName + "_init.mp4").toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING
                );
            }
        } catch (Exception e) {
            logger.error("Could not copy init file for {}", sessionKey, e);
        }

        ChronicleRecordingTask task = new ChronicleRecordingTask(userId, chronicleName, chronicleRecordingDir, cleanChronicleName, absoluteStartTimeMs);
        activeChronicleTasks.put(sessionKey, task);
        new Thread(task).start();
    }

    public void stopRecording(String userId, String chronicleName, long absoluteEndTimeMs) {
        String sessionKey = userId + ":" + chronicleName;
        ChronicleRecordingTask task = activeChronicleTasks.remove(sessionKey);
        if (task != null) {
            task.setEndTime(absoluteEndTimeMs);
            task.stop();
            logger.info("Stopped recording task for {} at {}", sessionKey, absoluteEndTimeMs);
        }
    }

    public boolean isRecording(String userId, String chronicleName) {
        String sessionKey = userId + ":" + chronicleName;
        ChronicleRecordingTask task = activeChronicleTasks.get(sessionKey);
        return task != null && task.running;
    }

    private class ChronicleRecordingTask implements Runnable {
        private final String userId;
        private final String chronicleName;
        private final File dir;
        private final String cleanName;
        private final long startTimeMs;
        private volatile long endTimeMs = Long.MAX_VALUE;
        private volatile boolean running = true;
        private final List<SegmentInfo> segments = new ArrayList<>();
        private long lastProcessedSegment = -1;

        private static class SegmentInfo {
            String filename;
            String targetName;
            long startTime;
            public SegmentInfo(String filename, String targetName, long startTime) {
                this.filename = filename;
                this.targetName = targetName;
                this.startTime = startTime;
            }
        }

        public ChronicleRecordingTask(String userId, String chronicleName, File dir, String cleanName, long startTimeMs) {
            this.userId = userId;
            this.chronicleName = chronicleName;
            this.dir = dir;
            this.cleanName = cleanName;
            this.startTimeMs = startTimeMs;
        }

        public void setEndTime(long endTimeMs) { this.endTimeMs = endTimeMs; }
        public void stop() { running = false; }

        @Override
        public void run() {
            logger.info("Task started for {}/{} (start: {})", userId, chronicleName, startTimeMs);
            while (running || hasPendingSegments()) {
                processNewSegments();
                if (endTimeMs != Long.MAX_VALUE) {
                    truncateAndClean();
                    if (System.currentTimeMillis() > endTimeMs + 30000) break;
                }
                try {
                    Thread.sleep(2000);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            truncateAndClean();
            finalizeManifest();
        }

        private boolean hasPendingSegments() {
            if (endTimeMs == Long.MAX_VALUE) return false;
            long lastSegmentEndTime = continuousStartTime + (lastProcessedSegment + 1) * 1000;
            return lastSegmentEndTime < endTimeMs && (System.currentTimeMillis() < endTimeMs + 30000);
        }

        private void processNewSegments() {
            File masterM3u8 = new File("media/continuous/continuous.m3u8");
            if (!masterM3u8.exists()) return;

            try {
                List<String> lines = java.nio.file.Files.readAllLines(masterM3u8.toPath());
                for (String line : lines) {
                    if (line.startsWith("continuous_segment_") && line.endsWith(".m4s")) {
                        long segmentNum = Long.parseLong(line.substring(19, 24));
                        long segmentStartTime = continuousStartTime + segmentNum * 1000;
                        long segmentEndTime = segmentStartTime + 1000;
                        
                        if (segmentNum > lastProcessedSegment) {
                            if (segmentEndTime > startTimeMs && segmentStartTime < endTimeMs) {
                                linkSegment(line, segmentStartTime);
                                updateManifest();
                            }
                            lastProcessedSegment = segmentNum;
                        }
                    }
                }
            } catch (Exception e) {
                logger.error("Error processing segments for {}", chronicleName, e);
            }
        }

        private void linkSegment(String segmentName, long startTime) {
            File source = new File("media/continuous", segmentName);
            String targetName = cleanName + "_segment_" + String.format("%05d", segments.size()) + ".m4s";
            File target = new File(dir, targetName);
            try {
                if (target.exists()) target.delete();
                java.nio.file.Files.createLink(target.toPath(), source.toPath());
                segments.add(new SegmentInfo(segmentName, targetName, startTime));
            } catch (Exception e) {
                logger.error("Failed to link segment {} to {}", segmentName, targetName, e);
            }
        }

        private synchronized void truncateAndClean() {
            if (endTimeMs == Long.MAX_VALUE) return;

            List<SegmentInfo> toRemove = new ArrayList<>();
            for (SegmentInfo seg : segments) {
                if (seg.startTime >= endTimeMs) {
                    toRemove.add(seg);
                }
            }

            if (!toRemove.isEmpty()) {
                logger.info("Truncating {} segments from {}", toRemove.size(), chronicleName);
                segments.removeAll(toRemove);
                for (SegmentInfo seg : toRemove) {
                    File f = new File(dir, seg.targetName);
                    if (f.exists()) f.delete();
                }
                updateManifest();
            }
        }

        private void updateManifest() {
            File manifest = new File(dir, cleanName + ".m3u8");
            try (java.io.PrintWriter writer = new java.io.PrintWriter(manifest)) {
                writer.println("#EXTM3U");
                writer.println("#EXT-X-VERSION:7");
                writer.println("#EXT-X-TARGETDURATION:2");
                writer.println("#EXT-X-MEDIA-SEQUENCE:0");
                writer.println("#EXT-X-MAP:URI=\"" + cleanName + "_init.mp4\"");
                for (SegmentInfo seg : segments) {
                    writer.println("#EXTINF:1.000,");
                    writer.println(seg.targetName);
                }
            } catch (Exception e) {
                logger.error("Failed to update manifest for {}", chronicleName, e);
            }
        }

        private void finalizeManifest() {
            File manifest = new File(dir, cleanName + ".m3u8");
            try (java.io.PrintWriter writer = new java.io.PrintWriter(new java.io.FileWriter(manifest, true))) {
                writer.println("#EXT-X-ENDLIST");
            } catch (Exception e) {
                logger.error("Failed to finalize manifest for {}", chronicleName, e);
            }
        }
    }
}
