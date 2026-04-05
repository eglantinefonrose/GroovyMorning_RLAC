package recording.service;

import org.quartz.*;
import org.quartz.impl.StdSchedulerFactory;
import org.quartz.impl.matchers.GroupMatcher;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.Calendar;

public class RecordingScheduler {

    private static final Logger logger = LoggerFactory.getLogger(RecordingScheduler.class);
    private static RecordingScheduler instance;
    private Scheduler scheduler;

    public static synchronized RecordingScheduler getInstance() {
        if (instance == null) {
            instance = new RecordingScheduler();
        }
        return instance;
    }

    private RecordingScheduler() {
        try {
            scheduler = StdSchedulerFactory.getDefaultScheduler();
            if (!scheduler.isStarted()) {
                scheduler.start();
            }
        } catch (SchedulerException e) {
            logger.error("❌ Erreur lors de l'initialisation du scheduler", e);
            throw new RuntimeException(e);
        }
    }

    public void cancelAllJobsForUser(String userID) throws SchedulerException {
        String groupName = "recordings";
        Set<JobKey> jobKeys = scheduler.getJobKeys(GroupMatcher.jobGroupEquals(groupName));
        int count = 0;
        for (JobKey jobKey : jobKeys) {
            // Le jobName est "radioRecording_" + userID + suffix
            if (jobKey.getName().startsWith("radioRecording_" + userID)) {
                scheduler.deleteJob(jobKey);
                count++;
                logger.info("🗑️ Job {} annulé pour l'utilisateur {}.", jobKey.getName(), userID);
            }
        }
        
        // Nettoyer aussi le stockage
        ScheduleStorage.getInstance().clearAllSchedulesForUser(userID);
        
        if (count > 0) {
            logger.info("✅ {} jobs d'enregistrement annulés pour l'utilisateur {}.", count, userID);
        } else {
            logger.info("ℹ️ Aucun job d'enregistrement actif trouvé pour l'utilisateur {}.", userID);
        }
    }

    private void cancelJobForUser(String userID) throws SchedulerException {
        String jobName = "radioRecording_" + userID;
        String groupName = "recordings";
        JobKey jobKey = new JobKey(jobName, groupName);

        if (scheduler.checkExists(jobKey)) {
            scheduler.deleteJob(jobKey);
            logger.info("🗑️ Ancien job pour l'utilisateur {} annulé.", userID);
        }
    }

    public ScheduleStorage.ScheduleData getScheduleForUser(String userID) {
        return ScheduleStorage.getInstance().getScheduleForUser(userID);
    }

    public Map<String, ScheduleStorage.ScheduleData> getSchedules() {
        return ScheduleStorage.getInstance().getSchedules();
    }

    public void shutdownScheduler() {
        try {
            if (scheduler != null && scheduler.isStarted()) {
                scheduler.shutdown(true); // Attendre la fin des jobs en cours
                logger.info("✅ Scheduler Quartz arrêté.");
            }
        } catch (SchedulerException e) {
            logger.error("❌ Erreur lors de l'arrêt du scheduler", e);
        }
    }
}