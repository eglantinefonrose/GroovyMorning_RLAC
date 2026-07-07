package recording.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import service.DatabaseService;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class ChroniclesManagerService {
    private static final Logger logger = LoggerFactory.getLogger(ChroniclesManagerService.class);
    private static ChroniclesManagerService instance;
    private final DatabaseService dbService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ChroniclesManagerService() {
        this.dbService = DatabaseService.getInstance();
    }

    public static synchronized ChroniclesManagerService getInstance() {
        if (instance == null) {
            instance = new ChroniclesManagerService();
        }
        return instance;
    }

    public boolean syncChroniclesWithExternalApi(String userID) {
        String pythonApiUrl = System.getenv().getOrDefault("PYTHON_API_URL", "http://localhost:8001");
        String url = pythonApiUrl + "/api/chronicles";

        try (HttpClient client = HttpClient.newHttpClient()) {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .GET()
                    .build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                List<Chronicle> dailyChronicles = objectMapper.readValue(response.body(), new TypeReference<List<Chronicle>>() {});
                
                // Calculer les endTimes car l'API ne fournit que le début
                if (dailyChronicles != null) {
                    for (int i = 0; i < dailyChronicles.size(); i++) {
                        Chronicle current = dailyChronicles.get(i);
                        if (i < dailyChronicles.size() - 1) {
                            current.setEndTime(dailyChronicles.get(i + 1).getStartTime());
                        } else {
                            // Par défaut +10 min pour la dernière chronique
                            current.setEndTime(current.getStartTime() + 600);
                        }
                    }
                }

                List<Chronicle> currentChronicles = dbService.getChronicles(userID);

                if (dailyChronicles != null && !dailyChronicles.equals(currentChronicles)) {
                    logger.info("🔄 Différence détectée avec la grille du jour. Mise à jour pour l'utilisateur {}.", userID);
                    dbService.removeChroniclesForUser(userID);
                    for (int i = 0; i < dailyChronicles.size(); i++) {
                        dbService.addChronicle(userID, dailyChronicles.get(i), i + 1);
                    }
                    dbService.setUserHasCustomList(userID, true);
                    return true;
                }
            } else {
                logger.warn("⚠️ Impossible de récupérer la grille du jour (Status: {}).", response.statusCode());
            }
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la synchronisation avec l'API Python", e);
        }
        return false;
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
            chronicles = RadioProgramService.getAllChronicles();
        }

        // Récupérer l'heure de début de l'utilisateur (base time)
        DatabaseService.UserConfig config = dbService.getUserConfig(userID);
        int userBaseSeconds = config.baseHour * 3600 + config.baseMinute * 60;
        
        // Référence théorique : La matinale commence à 07:00:00 sur France Inter
        int referenceSeconds = 7 * 3600; 

        return chronicles.stream()
                .filter(c -> (referenceSeconds + c.getStartTime()) >= userBaseSeconds)
                .collect(Collectors.toList());
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
