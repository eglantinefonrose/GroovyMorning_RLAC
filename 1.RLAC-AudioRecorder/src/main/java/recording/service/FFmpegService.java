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
    private double masterOffsetSeconds = 0.0; // Offset calculé par rapport au serveur Python
    private final boolean disableMasterSync = Boolean.parseBoolean(System.getenv().getOrDefault("DISABLE_MASTER_SYNC", "false"));

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
                "-i", "http://icecast.radiofrance.fr/franceinter-hifi.aac",
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

            // Démarrer la synchronisation initiale si elle n'est pas désactivée
            if (!disableMasterSync) {
                startInitialSync();
            } else {
                logger.info("🚫 Master sync is disabled by configuration.");
            }

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

    private void startInitialSync() {
        new Thread(() -> {
            // On attend que le segment 00005 soit généré (environ 6-7s après le début)
            File segmentFile = new File("media/continuous/continuous_segment_00005.m4s");
            logger.info("⏳ Waiting for segment 00005 for initial master sync...");
            
            for (int i = 0; i < 60; i++) {
                if (segmentFile.exists() && segmentFile.length() > 0) break;
                try { Thread.sleep(1000); } catch (InterruptedException e) { return; }
            }
            
            if (segmentFile.exists()) {
                calculateMasterOffset(segmentFile, 5);
            } else {
                logger.error("❌ Master sync failed: segment 00005 never appeared.");
            }
        }).start();
    }

    private void calculateMasterOffset(File segmentFile, int positionInSeconds) {
        String fingerprintPath = "media/fingerprint_" + System.currentTimeMillis() + ".raw";
        String pythonApiUrl = System.getenv().getOrDefault("PYTHON_API_URL", "http://localhost:8001");
        String userId = service.DatabaseService.getInstance().getLocalUserId();

        // Création d'une empreinte légère : 2s d'audio sous-échantillonné à 4000Hz mono
        // On prend le segment actuel et celui d'avant pour avoir 2 secondes
        File prevSegment = new File(segmentFile.getParent(), String.format("continuous_segment_%05d.m4s", positionInSeconds - 1));
        
        List<String> cmd = new ArrayList<>(List.of(FFMPEG_PATH, "-y"));
        if (prevSegment.exists()) {
            cmd.addAll(List.of("-i", prevSegment.getAbsolutePath()));
        }
        cmd.addAll(List.of("-i", segmentFile.getAbsolutePath(), "-filter_complex", "concat=n=" + (prevSegment.exists() ? "2" : "1") + ":v=0:a=1", "-f", "s16le", "-ar", "4000", "-ac", "1", fingerprintPath));

        try {
            Process p = new ProcessBuilder(cmd).start();
            p.waitFor();

            if (new File(fingerprintPath).exists()) {
                logger.info("🚀 Sending fingerprint for sync (userId: {})", userId);
                ProcessBuilder sendPb = new ProcessBuilder(
                        "curl", "-s", "-X", "POST",
                        pythonApiUrl + "/api/sync_offset?userId=" + userId + "&positionInSeconds=" + positionInSeconds,
                        "--data-binary", "@" + fingerprintPath
                );
                Process sendProcess = sendPb.start();
                BufferedReader reader = new BufferedReader(new InputStreamReader(sendProcess.getInputStream()));
                String response = reader.readLine();
                sendProcess.waitFor();
                
                if (response != null && response.contains("\"delta\"")) {
                    // Exemple de réponse : {"delta": 3.45, "score": 0.92}
                    org.json.JSONObject json = new org.json.JSONObject(response);
                    double delta = json.getDouble("delta");
                    double score = json.getDouble("score");
                    if (score > 0.7) {
                        this.masterOffsetSeconds = delta;
                        logger.info("✅ MASTER SYNC SUCCESS: Offset = {}s (Score: {})", delta, score);
                    } else {
                        logger.warn("⚠️ Master sync confidence too low: {} (Score: {})", delta, score);
                    }
                }
                new File(fingerprintPath).delete();
            }
        } catch (Exception e) {
            logger.error("Error during master sync calculation", e);
        }
    }

    public double getMasterOffsetSeconds() {
        return masterOffsetSeconds;
    }

    public void stopContinuousRecording() {
        if (continuousProcess != null && continuousProcess.isAlive()) {
            logger.info("Stopping continuous recording");
            continuousProcess.destroy();
            continuousProcess = null;
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
        
        File userDir = new File("media/userID_" + userId);
        if (!userDir.exists() && !userId.startsWith("user_")) {
            File altDir = new File("media/userID_user_" + userId);
            if (altDir.exists()) {
                userDir = altDir;
            }
        }
        
        File baseSessionDir = new File(userDir, folderName);
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
