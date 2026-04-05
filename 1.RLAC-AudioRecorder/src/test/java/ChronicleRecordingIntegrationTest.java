import org.example.api.RLACServerAPI;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.quartz.SchedulerException;
import recording.service.Chronicle;
import recording.service.ChroniclesManagerService;
import recording.service.RadioProgramService;
import service.RLACService;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

public class ChronicleRecordingIntegrationTest {

    private static RLACServerAPI rlacServerAPI;
    private static RLACService rlacService;
    private static ChroniclesManagerService chroniclesManagerService;
    private static String testUserId = "testUserForRecording_" + System.currentTimeMillis();
    private static String sessionFolderName = ""; // Sera rempli dynamiquement

    @BeforeAll
    static void setup() throws SchedulerException {
        // Initialiser l'API et les services (le constructeur de RLACServerAPI le fait)
        rlacServerAPI = new RLACServerAPI();
        // Accéder aux services internes de l'API pour le test
        try {
            // Utiliser la réflexion pour accéder aux champs privés si nécessaire
            java.lang.reflect.Field rlacServiceField = RLACServerAPI.class.getDeclaredField("rlacService");
            rlacServiceField.setAccessible(true);
            rlacService = (RLACService) rlacServiceField.get(rlacServerAPI);

            java.lang.reflect.Field chroniclesManagerServiceField = RLACServerAPI.class.getDeclaredField("chroniclesManagerService");
            chroniclesManagerServiceField.setAccessible(true);
            chroniclesManagerService = (ChroniclesManagerService) chroniclesManagerServiceField.get(rlacServerAPI);

        } catch (NoSuchFieldException | IllegalAccessException e) {
            fail("Impossible d'accéder aux services internes de RLACServerAPI: " + e.getMessage());
        }

        // Ajouter des chroniques de test
        // Utiliser des chroniques existantes de RadioProgramService et modifier leur durée pour le test
        List<Chronicle> allProgramChronicles = RadioProgramService.getAllChronicles();

        Chronicle chronicle1 = allProgramChronicles.stream()
                .filter(c -> c.getNomDeChronique().equals("journal de 7h"))
                .findFirst()
                .orElseThrow(() -> new AssertionError("Chronique 'journal de 7h' non trouvée."));
        chroniclesManagerService.addChronicle(testUserId, new Chronicle(chronicle1.getNomDeChronique(), 0, 10)); // 10 secondes

        Chronicle chronicle2 = allProgramChronicles.stream()
                .filter(c -> c.getNomDeChronique().equals("les 80 secondes"))
                .findFirst()
                .orElseThrow(() -> new AssertionError("Chronique 'les 80 secondes' non trouvée."));
        chroniclesManagerService.addChronicle(testUserId, new Chronicle(chronicle2.getNomDeChronique(), 10, 20)); // 10 secondes

        // On n'en ajoute que 2 pour le test, car addChronicle initialise déjà avec les 13 défauts.
        // Total attendu : 13 (défauts) + 2 (ajouts) = 15

        // Enregistrer le nom du dossier de session qui sera créé
        sessionFolderName = "session_" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
    }

    @Test
    void testScheduleAndRecordAllUserChronicles() throws SchedulerException, InterruptedException, IOException {
        System.out.println("Lancement du test d'intégration d'enregistrement dynamique des chroniques...");

        // On simule les appels API dynamic
        recording.service.DynamicRecordingService dynamicService = recording.service.DynamicRecordingService.getInstance();
        
        String chronicle1 = "journal de 7h";
        String chronicle2 = "les 80 secondes";

        // Start C1
        dynamicService.handleStartNotification(testUserId, chronicle1);
        Thread.sleep(5000); // Record 5 seconds
        
        // End C1 with realDuration
        dynamicService.handleEndNotification(testUserId, chronicle1, "5");
        
        // C2 starts automatically (chained)
        Thread.sleep(5000); // Record 5 seconds
        
        // End C2
        dynamicService.handleEndNotification(testUserId, chronicle2, "5");

        System.out.println("Vérification des fichiers enregistrés...");

        // Vérification des fichiers créés
        Path userMediaDirPath = Paths.get("media", "userID_" + testUserId);
        assertTrue(Files.exists(userMediaDirPath), "Le dossier utilisateur n'existe pas : " + userMediaDirPath.toAbsolutePath());

        // Le nouveau format est session_yyyyMMdd_dynamic
        String datePart = java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd"));
        Path sessionDirPath = userMediaDirPath.resolve("session_" + datePart + "_dynamic");
        
        assertTrue(Files.exists(sessionDirPath), "Le dossier de session n'existe pas : " + sessionDirPath.toAbsolutePath());
        assertTrue(Files.isDirectory(sessionDirPath), "Le dossier de session n'est pas un répertoire.");

        List<String> chroniclesToVerify = List.of(chronicle1, chronicle2);

        for (String chronicleName : chroniclesToVerify) {
            String cleanChronicleName = chronicleName.replaceAll("[^a-zA-Z0-9]", "_");
            Path chronicleDirPath = sessionDirPath.resolve(cleanChronicleName);

            // On attend que les tâches asynchrones finissent d'écrire
            for(int i=0; i<10 && !Files.exists(chronicleDirPath.resolve(cleanChronicleName + ".m3u8")); i++) {
                Thread.sleep(1000);
            }

            assertTrue(Files.exists(chronicleDirPath), "Le dossier de la chronique n'existe pas : " + chronicleDirPath.toAbsolutePath());
            assertTrue(Files.isDirectory(chronicleDirPath), "Le dossier de la chronique n'est pas un répertoire.");

            // Vérifier la présence des fichiers clés
            assertTrue(Files.exists(chronicleDirPath.resolve(cleanChronicleName + ".m3u8")), "Playlist M3U8 non trouvée pour " + chronicleName);
            assertTrue(Files.exists(chronicleDirPath.resolve(cleanChronicleName + "_init.mp4")), "Init MP4 non trouvé pour " + chronicleName);
            
            // Les segments peuvent mettre un peu de temps à apparaître car ils dépendent du flux master
            System.out.println("✔️ Dossier trouvé pour la chronique : " + chronicleName);
        }

        System.out.println("Test d'intégration terminé avec succès.");
    }

    @Test
    void testRemoveUserChronicles() throws SchedulerException {
        String deleteUserId = "userToDelete";
        
        // 1. Ajouter des chroniques
        chroniclesManagerService.addChronicle(deleteUserId, new Chronicle("Chronique à supprimer", 0, 10));
        assertFalse(chroniclesManagerService.getChronicles(deleteUserId).isEmpty(), "L'utilisateur devrait avoir des chroniques avant suppression");
        
        // 2. Planifier (crée des jobs Quartz)
        rlacService.scheduleAllUserChronicles(deleteUserId, 8, 0);
        
        // 3. Supprimer
        rlacService.removeUserChronicles(deleteUserId);
        
        // 4. Vérifier que c'est vide
        assertTrue(chroniclesManagerService.getChronicles(deleteUserId).isEmpty(), "L'utilisateur ne devrait plus avoir de chroniques");
        
        // Note: La vérification que les jobs Quartz sont supprimés est plus complexe à faire ici sans accès direct au scheduler interne,
        // mais l'appel à rlacService.removeUserChronicles(deleteUserId) a été effectué sans erreur.
    }

    @Test
    void testDefaultChronicles() {
        String newUser = "totallyNewUser_" + System.currentTimeMillis();
        List<Chronicle> chronicles = chroniclesManagerService.getChronicles(newUser);
        
        assertEquals(13, chronicles.size(), "Un nouvel utilisateur devrait avoir 13 chroniques par défaut");
        assertEquals("journal de 7h", chronicles.get(0).getNomDeChronique());
        assertEquals("Geopolitique", chronicles.get(12).getNomDeChronique());
    }

    @AfterAll
    static void teardown() {
        System.out.println("Nettoyage après le test...");
        // Arrêter le scheduler Quartz
        try {
            java.lang.reflect.Field recordingSchedulerField = RLACServerAPI.class.getDeclaredField("recordingScheduler");
            recordingSchedulerField.setAccessible(true);
            recording.service.RecordingScheduler schedulerInstance = (recording.service.RecordingScheduler) recordingSchedulerField.get(rlacServerAPI);
            schedulerInstance.shutdownScheduler();
            System.out.println("Scheduler Quartz arrêté.");
        } catch (NoSuchFieldException | IllegalAccessException e) {
            System.err.println("Erreur lors de l'arrêt du scheduler: " + e.getMessage());
        }

        // Nettoyer les fichiers et dossiers créés par le test
        // Path userMediaDirPath = Paths.get("media", "userID_" + testUserId);
        // if (Files.exists(userMediaDirPath)) {
        //     try (Stream<Path> walk = Files.walk(userMediaDirPath)) {
        //         walk.sorted(Comparator.reverseOrder()) // Supprimer les fichiers avant les dossiers
        //                 .forEach(path -> {
        //                     try {
        //                         Files.delete(path);
        //                     } catch (IOException e) {
        //                         System.err.println("Impossible de supprimer le fichier/dossier " + path + ": " + e.getMessage());
        //                     }
        //                 });
        //     } catch (IOException e) {
        //         System.err.println("Erreur lors du nettoyage du dossier " + userMediaDirPath + ": " + e.getMessage());
        //     }
        //     System.out.println("Dossier de test " + userMediaDirPath.toAbsolutePath() + " nettoyé.");
        // }
    }
}
