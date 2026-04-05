package recording.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.*;

public class ScheduleStorage {

    private static final Logger logger = LoggerFactory.getLogger(ScheduleStorage.class);
    private static final String STORAGE_FILE = "schedule.json";
    private static final ObjectMapper objectMapper = new ObjectMapper();

    // Singleton
    private static ScheduleStorage instance;
    private Map<String, ScheduleData> schedules = new HashMap<>();

    private ScheduleStorage() {
        loadFromFile();
    }

    public static synchronized ScheduleStorage getInstance() {
        if (instance == null) {
            instance = new ScheduleStorage();
        }
        return instance;
    }

    // Classe interne pour les données
    public static class ScheduleData {
        private int hour;
        private int minute;
        private int duration;
        private String uuid;
        private long createdAt;
        private long nextRunTime;

        public ScheduleData() {}

        public ScheduleData(int hour, int minute, int duration, String uuid) {
            this.hour = hour;
            this.minute = minute;
            this.duration = duration;
            this.uuid = uuid;
            this.createdAt = System.currentTimeMillis();

            // Calculer le prochain run
            Calendar cal = Calendar.getInstance();
            cal.set(Calendar.HOUR_OF_DAY, hour);
            cal.set(Calendar.MINUTE, minute);
            cal.set(Calendar.SECOND, 0);
            cal.set(Calendar.MILLISECOND, 0);

            // Si l'heure est déjà passée aujourd'hui, ajouter un jour
            if (cal.getTimeInMillis() < System.currentTimeMillis()) {
                cal.add(Calendar.DAY_OF_MONTH, 1);
            }
            this.nextRunTime = cal.getTimeInMillis();
        }

        // Getters et Setters
        public int getHour() { return hour; }
        public void setHour(int hour) { this.hour = hour; }

        public int getMinute() { return minute; }
        public void setMinute(int minute) { this.minute = minute; }

        public int getDuration() { return duration; }
        public void setDuration(int duration) { this.duration = duration; }

        public String getUuid() { return uuid; }
        public void setUuid(String uuid) { this.uuid = uuid; }

        public long getCreatedAt() { return createdAt; }
        public void setCreatedAt(long createdAt) { this.createdAt = createdAt; }

        public long getNextRunTime() { return nextRunTime; }
        public void setNextRunTime(long nextRunTime) { this.nextRunTime = nextRunTime; }

        // getFormattedTime est une valeur calculée et ne doit pas être sérialisée/désérialisée.
        // Il n'y a donc pas de setter ni de champ direct pour cela.
    }

    public void saveSchedule(String userId, int hour, int minute, int duration, String uuid) {
        // Crée un nouveau schedule
        ScheduleData newSchedule = new ScheduleData(hour, minute, duration, uuid);

        // Soit ajoute (si nouveau user), soit remplace (si user existant)
        schedules.put(userId, newSchedule);

        // Sauvegarde dans le fichier, la map 'schedules' contient déjà les données à jour
        saveToFile();

        logger.info("✅ Nouveau schedule enregistré pour l'utilisateur {} - {}:{} (durée: {}s)",
                userId, hour, minute, duration);
    }

    public Map<String, ScheduleData> getSchedules() {
        return Collections.unmodifiableMap(schedules);
    }

    public ScheduleData getScheduleForUser(String userId) {
        return schedules.get(userId);
    }

    private synchronized void saveToFile() {
        try {
            objectMapper.writerWithDefaultPrettyPrinter()
                    .writeValue(new File(STORAGE_FILE), schedules);
            logger.debug("💾 Schedules sauvegardés dans {}", STORAGE_FILE);
        } catch (IOException e) {
            logger.error("❌ Erreur sauvegarde schedule.json", e);
        }
    }

    private synchronized void loadFromFile() {
        File file = new File(STORAGE_FILE);
        if (!file.exists()) {
            logger.info("📁 Fichier schedule.json non trouvé, pas de schedule existant");
            schedules = new HashMap<>();
            return;
        }

        try {
            schedules = objectMapper.readValue(file, new TypeReference<Map<String, ScheduleData>>() {});
            if (schedules == null) {
                schedules = new HashMap<>();
            }
            logger.info("📂 Schedules chargés: {} utilisateurs", schedules.size());
        } catch (IOException e) {
            logger.error("❌ Erreur chargement schedule.json", e);
            schedules = new HashMap<>();
        }
    }

    public void clearSchedule(String userId) {
        if (schedules.remove(userId) != null) {
            saveToFile(); // Appelle la méthode simplifiée
            logger.info("🗑️ Schedule effacé pour l'utilisateur {}", userId);
        } else {
            logger.warn("🗑️ Tentative de suppression d'un schedule inexistant pour l'utilisateur {}", userId);
        }
    }

    public void clearAllSchedulesForUser(String userId) {
        boolean removed = schedules.keySet().removeIf(key -> key.equals(userId) || key.startsWith(userId + "#"));
        if (removed) {
            saveToFile();
            logger.info("🗑️ Tous les schedules pour l'utilisateur {} ont été effacés.", userId);
        } else {
            logger.warn("⚠️ Aucun schedule trouvé à effacer pour l'utilisateur {}", userId);
        }
    }
}