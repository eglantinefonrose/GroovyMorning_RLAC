package recording.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import service.DatabaseService;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class DynamicRecordingService {
    private static final Logger logger = LoggerFactory.getLogger(DynamicRecordingService.class);
    private static DynamicRecordingService instance;

    private final FFmpegService ffmpegService;
    private final Map<String, RecordingSession> activeSessions = new ConcurrentHashMap<>();
    private final Map<String, LocalDateTime> lastChronicleEndTime = new ConcurrentHashMap<>();
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
    private final ChroniclesManagerService chroniclesManagerService;

    private DynamicRecordingService() {
        this.ffmpegService = new FFmpegService();
        this.chroniclesManagerService = ChroniclesManagerService.getInstance();
    }

    public static synchronized DynamicRecordingService getInstance() {
        if (instance == null) {
            instance = new DynamicRecordingService();
        }
        return instance;
    }

    public FFmpegService getFFmpegService() {
        return ffmpegService;
    }

    private boolean isChronicleAuthorized(String userId, String chronicleName) {
        List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
        return userChronicles.stream()
                .anyMatch(c -> c.getNomDeChronique().equals(chronicleName));
    }

    public void handleStartNotification(String userId, String chronicleName) {
        handleStartNotification(userId, chronicleName, null);
    }

    public synchronized void handleStartNotification(String userId, String chronicleName, Integer deltaStartTimeInSeconds) {
        logger.info("Received START notification for user: {}, chronicle: {}, delta: {}", userId, chronicleName, deltaStartTimeInSeconds);
        
        if (!isChronicleAuthorized(userId, chronicleName)) {
            logger.warn("Ignoring START: Chronicle '{}' not authorized for user '{}'", chronicleName, userId);
            return;
        }

        // Démarrer l'enregistrement continu s'il n'est pas déjà lancé
        // C'est ici que le flux FFmpeg maître est initialisé
        ffmpegService.startContinuousRecording();

        DatabaseService.UserConfig config = DatabaseService.getInstance().getUserConfig(userId);
        int currentOffset = calculateCurrentOffset(config);
        
        // Si on a un delta, on calcule le temps de début par rapport au début du flux continu
        LocalDateTime absoluteStartTime;
        if (deltaStartTimeInSeconds != null) {
            long baseMs = ffmpegService.getContinuousStartTime();
            long targetMs = baseMs + (deltaStartTimeInSeconds * 1000L);
            absoluteStartTime = LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(targetMs), java.time.ZoneId.systemDefault());
            logger.info("Using delta start time: {}s from continuous start -> {}", deltaStartTimeInSeconds, absoluteStartTime);
        } else {
            // Si on a un temps de fin de la chronique précédente, on l'utilise comme temps de début
            absoluteStartTime = lastChronicleEndTime.get(userId);
            if (absoluteStartTime == null) {
                absoluteStartTime = LocalDateTime.now();
            }
        }

        String sessionKey = userId + ":" + chronicleName;
        RecordingSession session = activeSessions.get(sessionKey);
        
        if (session != null && session.isRecording()) {
            logger.warn("Recording already in progress for session key: {}. Ignoring START notification.", sessionKey);
            return;
        }

        if (session == null) {
            session = new RecordingSession(userId, chronicleName);
            activeSessions.put(sessionKey, session);
        }
        
        session.setStartTimecode(currentOffset);
        session.setAbsoluteStartTime(absoluteStartTime);
        session.setStartReceived(true);

        if (session.shouldStart()) {
            startRecording(session);
        }
    }

    public synchronized void handleEndNotification(String userId, String chronicleName, String realDuration) {
        logger.info("Received END notification for user: {}, chronicle: {}, realDuration: {}", userId, chronicleName, realDuration);
        
        if (!isChronicleAuthorized(userId, chronicleName)) {
            logger.warn("Ignoring END: Chronicle '{}' not authorized for user '{}'", chronicleName, userId);
            return;
        }

        double durationSeconds = parseDuration(realDuration);
        
        String sessionKey = userId + ":" + chronicleName;
        RecordingSession session = activeSessions.get(sessionKey);
        
        if (session != null) {
            LocalDateTime realEnd = session.getAbsoluteStartTime().plusNanos((long)(durationSeconds * 1_000_000_000L));
            lastChronicleEndTime.put(userId, realEnd);
            
            if (session.isRecording()) {
                stopRecording(session);
            }
            activeSessions.remove(sessionKey);
        } else {
            // Même si la session n'existe pas, on essaie de calculer un temps de fin théorique si possible
            // ou on utilise l'heure actuelle
            lastChronicleEndTime.put(userId, LocalDateTime.now());
        }
    }

    private double parseDuration(String durationStr) {
        if (durationStr == null || durationStr.isEmpty() || durationStr.equals("realDuration")) {
            return 0;
        }
        try {
            // Format "10min33secondes"
            if (durationStr.contains("min") || durationStr.contains("secondes")) {
                double total = 0;
                java.util.regex.Pattern minPattern = java.util.regex.Pattern.compile("(\\d+)\\s*min");
                java.util.regex.Pattern secPattern = java.util.regex.Pattern.compile("(\\d+)\\s*secondes");
                
                java.util.regex.Matcher minMatcher = minPattern.matcher(durationStr);
                if (minMatcher.find()) {
                    total += Double.parseDouble(minMatcher.group(1)) * 60;
                }
                
                java.util.regex.Matcher secMatcher = secPattern.matcher(durationStr);
                if (secMatcher.find()) {
                    total += Double.parseDouble(secMatcher.group(1));
                }
                return total;
            }
            return Double.parseDouble(durationStr);
        } catch (Exception e) {
            logger.warn("Could not parse duration: {}. Defaulting to 0.", durationStr);
            return 0;
        }
    }

    private int calculateCurrentOffset(DatabaseService.UserConfig config) {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime baseTime = now.withHour(config.baseHour).withMinute(config.baseMinute).withSecond(0).withNano(0);
        return (int) java.time.Duration.between(baseTime, now).getSeconds();
    }

    private void checkAndStopContinuousRecording() {
        if (activeSessions.isEmpty()) {
            logger.info("No active sessions remaining. Stopping continuous recording.");
            ffmpegService.stopContinuousRecording();
            lastChronicleEndTime.clear();
        }
    }

    private void startRecording(RecordingSession session) {
        // Dossier de session unique par jour pour regrouper les chroniques
        String datePart = LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd"));
        String folderName = "session_" + datePart + "_dynamic"; 
        session.setFolderName(folderName);
        
        long startTimeMs = session.getAbsoluteStartTime().atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli();
        
        ffmpegService.startRecording(session.getUserId(), session.getChronicleName(), folderName, startTimeMs);
        session.setRecording(true);
        
        scheduler.schedule(() -> {
            if (session.isRecording()) {
                logger.warn("Safety timeout reached for session {}", session.getChronicleName());
                stopRecording(session);
            }
        }, 1, TimeUnit.HOURS);
    }

    private void stopRecording(RecordingSession session) {
        long endTimeMs = lastChronicleEndTime.containsKey(session.getUserId()) ? 
            lastChronicleEndTime.get(session.getUserId()).atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli() :
            System.currentTimeMillis();
            
        ffmpegService.stopRecording(session.getUserId(), session.getChronicleName(), endTimeMs);
        session.setRecording(false);
        logger.info("Recording stopped for {}", session.getChronicleName());
    }

    public void stopAll() {
        logger.info("Stopping all recording sessions and continuous flow...");
        for (RecordingSession session : activeSessions.values()) {
            if (session.isRecording()) {
                stopRecording(session);
            }
        }
        activeSessions.clear();
        ffmpegService.stopContinuousRecording();
        lastChronicleEndTime.clear();
    }

    private static class RecordingSession {
        private final String userId;
        private final String chronicleName;
        private int startTimecode;
        private int endTimecode;
        private LocalDateTime absoluteStartTime;
        private LocalDateTime absoluteEndTime;
        private boolean startReceived = false;
        private boolean endReceived = false;
        private boolean isRecording = false;
        private String folderName;

        public RecordingSession(String userId, String chronicleName) {
            this.userId = userId;
            this.chronicleName = chronicleName;
        }

        public String getUserId() { return userId; }
        public String getChronicleName() { return chronicleName; }
        public int getStartTimecode() { return startTimecode; }
        public void setStartTimecode(int startTimecode) { this.startTimecode = startTimecode; }
        public int getEndTimecode() { return endTimecode; }
        public void setEndTimecode(int endTimecode) { this.endTimecode = endTimecode; }
        public LocalDateTime getAbsoluteStartTime() { return absoluteStartTime; }
        public void setAbsoluteStartTime(LocalDateTime absoluteStartTime) { this.absoluteStartTime = absoluteStartTime; }
        public LocalDateTime getAbsoluteEndTime() { return absoluteEndTime; }
        public void setAbsoluteEndTime(LocalDateTime absoluteEndTime) { this.absoluteEndTime = absoluteEndTime; }
        public boolean isStartReceived() { return startReceived; }
        public void setStartReceived(boolean startReceived) { this.startReceived = startReceived; }
        public boolean isEndReceived() { return endReceived; }
        public void setEndReceived(boolean endReceived) { this.endReceived = endReceived; }
        public boolean isRecording() { return isRecording; }
        public void setRecording(boolean recording) { isRecording = recording; }
        public String getFolderName() { return folderName; }
        public void setFolderName(String folderName) { this.folderName = folderName; }

        public boolean shouldStart() {
            return startReceived && !isRecording && !endReceived;
        }
    }
}
