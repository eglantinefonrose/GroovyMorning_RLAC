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
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class ChroniclesManagerService {
    private static final Logger logger = LoggerFactory.getLogger(ChroniclesManagerService.class);
    private static ChroniclesManagerService instance;
    private final DatabaseService dbService;
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    // Référence théorique : La matinale commence à 07:00:00 sur France Inter
    public static final int REFERENCE_SECONDS = 7 * 3600; 

    public ChroniclesManagerService() {
        this.dbService = DatabaseService.getInstance();
    }

    public static synchronized ChroniclesManagerService getInstance() {
        if (instance == null) {
            instance = new ChroniclesManagerService();
        }
        return instance;
    }

    boolean areChroniclesListsEqual(List<Chronicle> list1, List<Chronicle> list2) {
        if (list1 == list2) return true;
        if (list1 == null || list2 == null) return false;
        if (list1.size() != list2.size()) return false;

        List<Chronicle> sorted1 = list1.stream()
                .sorted(Comparator.comparing(Chronicle::getStartTime, Comparator.nullsFirst(Integer::compareTo))
                        .thenComparing(Chronicle::getEndTime, Comparator.nullsFirst(Integer::compareTo))
                        .thenComparing(Chronicle::getNomDeChronique, Comparator.nullsFirst(String::compareTo)))
                .collect(Collectors.toList());

        List<Chronicle> sorted2 = list2.stream()
                .sorted(Comparator.comparing(Chronicle::getStartTime, Comparator.nullsFirst(Integer::compareTo))
                        .thenComparing(Chronicle::getEndTime, Comparator.nullsFirst(Integer::compareTo))
                        .thenComparing(Chronicle::getNomDeChronique, Comparator.nullsFirst(String::compareTo)))
                .collect(Collectors.toList());

        return sorted1.equals(sorted2);
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
                
                if (dailyChronicles == null) {
                    return false;
                }

                // Calculer les endTimes car l'API ne fournit que le début
                for (int i = 0; i < dailyChronicles.size(); i++) {
                    Chronicle current = dailyChronicles.get(i);
                    if (i < dailyChronicles.size() - 1) {
                        current.setEndTime(dailyChronicles.get(i + 1).getStartTime());
                    } else {
                        // Par défaut +10 min pour la dernière chronique
                        current.setEndTime(current.getStartTime() + 600);
                    }
                }

                // Récupérer la config du user pour filtrer
                DatabaseService.UserConfig config = dbService.getUserConfig(userID);
                int userBaseSeconds = config.baseHour * 3600 + config.baseMinute * 60;

                // Filtrer la grille du jour pour ne garder que ce qui est après l'heure de base
                List<Chronicle> filteredDaily = dailyChronicles.stream()
                        .filter(c -> (REFERENCE_SECONDS + c.getStartTime()) >= userBaseSeconds)
                        .collect(Collectors.toList());

                // Filtrer les chroniques actuelles en base pour la comparaison
                List<Chronicle> currentChronicles = dbService.getChronicles(userID).stream()
                        .filter(c -> (REFERENCE_SECONDS + c.getStartTime()) >= userBaseSeconds)
                        .collect(Collectors.toList());

                if (!areChroniclesListsEqual(filteredDaily, currentChronicles)) {
                    logDifferences(filteredDaily, currentChronicles);
                    logger.info("🔄 Différence détectée avec la grille du jour (après baseHour). Mise à jour pour l'utilisateur {}.", userID);
                    
                    // On remplace par la nouvelle version filtrée
                    dbService.removeChroniclesForUser(userID);
                    for (int i = 0; i < filteredDaily.size(); i++) {
                        dbService.addChronicle(userID, filteredDaily.get(i), i + 1);
                    }
                    dbService.setUserHasCustomList(userID, true);
                    return true;
                } else {
                    logger.info("✅ La grille de l'utilisateur {} est déjà à jour (après baseHour).", userID);
                }
            } else {
                logger.warn("⚠️ Impossible de récupérer la grille du jour (Status: {}).", response.statusCode());
            }
        } catch (Exception e) {
            logger.error("❌ Erreur lors de la synchronisation avec l'API Python", e);
        }
        return false;
    }

    private void logDifferences(List<Chronicle> daily, List<Chronicle> current) {
        logger.info("--- 📊 Comparaison avec la grille de France Inter ---");

        Map<String, Chronicle> currentMap = current.stream()
                .collect(Collectors.toMap(Chronicle::getNomDeChronique, c -> c, (a, b) -> a));
        Map<String, Chronicle> dailyMap = daily.stream()
                .collect(Collectors.toMap(Chronicle::getNomDeChronique, c -> c, (a, b) -> a));

        // Nouveautés ou modifications dans France Inter
        for (Chronicle d : daily) {
            String name = d.getNomDeChronique();
            if (!currentMap.containsKey(name)) {
                logger.info("[NOUVEAU] {} (Début: {}, Fin: {})", name, formatSecondsToTime(d.getStartTime()), formatSecondsToTime(d.getEndTime()));
            } else {
                Chronicle cur = currentMap.get(name);
                if (!d.equals(cur)) {
                    logger.info("[MODIFIÉ] {} : {} - {} -> {} - {}", name,
                            formatSecondsToTime(cur.getStartTime()), formatSecondsToTime(cur.getEndTime()),
                            formatSecondsToTime(d.getStartTime()), formatSecondsToTime(d.getEndTime()));
                }
            }
        }

        // Supprimés de France Inter
        for (Chronicle cur : current) {
            String name = cur.getNomDeChronique();
            if (!dailyMap.containsKey(name)) {
                logger.info("[SUPPRIMÉ] {}", name);
            }
        }
        logger.info("--- Fin de la comparaison ---");
    }

    private String formatSecondsToTime(Integer secondsFromReference) {
        if (secondsFromReference == null) return "??:??";
        int totalSeconds = REFERENCE_SECONDS + secondsFromReference;
        // Gérer le passage à minuit si nécessaire, bien que peu probable ici
        if (totalSeconds < 0) totalSeconds += 24 * 3600;
        int hour = (totalSeconds / 3600) % 24;
        int minute = (totalSeconds % 3600) / 60;
        return String.format("%02dh%02d", hour, minute);
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
        
        return chronicles.stream()
                .filter(c -> (REFERENCE_SECONDS + c.getStartTime()) >= userBaseSeconds)
                .map(c -> {
                    // Normaliser les offsets pour qu'ils soient relatifs à l'heure de base de l'utilisateur
                    int absoluteStart = REFERENCE_SECONDS + c.getStartTime();
                    int originalEndTime = c.getEndTime() != null ? c.getEndTime() : c.getStartTime() + 600;
                    int absoluteEnd = REFERENCE_SECONDS + originalEndTime;
                    
                    return new Chronicle(
                        c.getNomDeChronique(),
                        absoluteStart - userBaseSeconds,
                        absoluteEnd - userBaseSeconds
                    );
                })
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
