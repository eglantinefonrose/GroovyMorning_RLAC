package recording.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import service.DatabaseService;

import java.util.List;
import java.util.Map;

public class ChroniclesManagerService {
    private static final Logger logger = LoggerFactory.getLogger(ChroniclesManagerService.class);
    private static ChroniclesManagerService instance;
    private final DatabaseService dbService;

    public ChroniclesManagerService() {
        this.dbService = DatabaseService.getInstance();
    }

    public static synchronized ChroniclesManagerService getInstance() {
        if (instance == null) {
            instance = new ChroniclesManagerService();
        }
        return instance;
    }

    public void addChronicle(String userID, Chronicle chronicle) {
        // Si l'utilisateur n'avait pas de liste personnalisée, on l'initialise avec le programme par défaut
        if (!dbService.hasUserCustomList(userID)) {
            List<Chronicle> defaultChronicles = RadioProgramService.getAllChronicles();
            for (int i = 0; i < defaultChronicles.size(); i++) {
                dbService.addChronicle(userID, defaultChronicles.get(i), i + 1);
            }
            dbService.setUserHasCustomList(userID, true);
        }
        
        // Pour un ajout simple, on le met à la fin
        int nextOrder = dbService.getChronicles(userID).size() + 1;
        dbService.addChronicle(userID, chronicle, nextOrder);
        logger.info("Chronique {} ajoutée avec succès pour l'utilisateur {} dans SQLite (ordre {}).", 
                chronicle.getNomDeChronique(), userID, nextOrder);
    }

    public List<Chronicle> getChronicles(String userID) {
        List<Chronicle> chronicles = dbService.getChronicles(userID);
        if (chronicles.isEmpty() && !dbService.hasUserCustomList(userID)) {
            return RadioProgramService.getAllChronicles();
        }
        return chronicles;
    }

    public void removeChroniclesForUser(String userID) {
        // On supprime toutes les chroniques et on marque que l'utilisateur a une liste personnalisée (vide).
        dbService.removeChroniclesForUser(userID);
        dbService.setUserHasCustomList(userID, true);
        logger.info("🗑️ Toutes les chroniques pour l'utilisateur {} ont été supprimées de SQLite.", userID);
    }

    public Map<String, List<Chronicle>> getAllUserChronicles() {
        return dbService.getAllUserChronicles();
    }
}
