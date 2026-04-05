package service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import recording.service.ChroniclesManagerService;
import recording.service.RecordingScheduler;
import org.quartz.SchedulerException;

import java.io.File;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public class RLACService {

    private static final Logger logger = LoggerFactory.getLogger(RLACService.class);
    private final RecordingScheduler recordingScheduler;
    private final ChroniclesManagerService chroniclesManagerService;

    public RLACService(RecordingScheduler recordingScheduler, ChroniclesManagerService chroniclesManagerService) {
        this.recordingScheduler = recordingScheduler;
        this.chroniclesManagerService = chroniclesManagerService;
    }

    public void scheduleAllUserChronicles(String userID) throws SchedulerException {
        logger.info("Chronicles for user {} are now handled dynamically by Python notifications.", userID);
    }

    public void scheduleAllUserChronicles(String userID, int baseHour, int baseMinute) throws SchedulerException {
        logger.info("Chronicles for user {} are now handled dynamically (Base time: {}:{}).", userID, baseHour, baseMinute);
    }

    public void removeUserChronicles(String userID) throws SchedulerException {
        logger.info("Attempting to remove all chronicles and schedules for user: {}", userID);
        // 1. Annuler les jobs Quartz actifs et nettoyer ScheduleStorage
        recordingScheduler.cancelAllJobsForUser(userID);

        // 2. Supprimer les chroniques de la configuration (chronicles.json)
        chroniclesManagerService.removeChroniclesForUser(userID);
        logger.info("Successfully removed all chronicles and schedules for user: {}", userID);
    }

    public static Map<String, Object> findTodayFolder(String userID) throws Exception {
        // Générer le timestamp du jour
        String dateStr = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        String prefix = "session_" + dateStr;

        // Chercher dans le dossier media
        File userDir = new File("media", "userID_" + userID);
        if (!userDir.exists() || !userDir.isDirectory()) {
            throw new Exception("Le dossier 'media' n'existe pas ou n'est pas un répertoire.");
        }

        // Lister tous les dossiers qui commencent par le préfixe et trouver le plus récent
        Optional<File> latestFolder = Arrays.stream(userDir.listFiles())
                .filter(file -> file.isDirectory() && file.getName().startsWith(prefix))
                .max(Comparator.comparing(File::getName));

        Map<String, Object> result = new HashMap<>();

        if (latestFolder.isEmpty()) {
            result.put("found", false);
            result.put("message", "Aucun dossier trouvé pour aujourd'hui avec le préfixe: " + prefix);
            result.put("searchPattern", prefix + "*");
            return result;
        }

        File foundFolder = latestFolder.get();

        result.put("found", true);
        result.put("folderName", "userID_" + userID + "/" + foundFolder.getName());

        logger.info("📁 Dossier le plus récent trouvé : {}", foundFolder.getName());

        return result;
    }
}
