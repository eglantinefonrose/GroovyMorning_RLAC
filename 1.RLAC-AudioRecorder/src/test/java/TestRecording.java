import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import recording.service.RecordingScheduler;

public class TestRecording {

    private static final Logger logger = LoggerFactory.getLogger(TestRecording.class);

    /*public static void main(String[] args) {
        logger.info("🧪 TEST DE L'ENREGISTREMENT");
        logger.info("================================");

        // Vérifier ffmpeg
        if (!checkFFmpeg()) {
            logger.error("❌ ffmpeg n'est pas installé ou pas accessible");
            System.exit(1);
        }

        // Vérifier l'accès au stream
        if (!checkStreamAccess()) {
            logger.error("⚠️ Le stream n'est peut-être pas accessible");
        }

        RecordingScheduler scheduler = RecordingScheduler.getInstance();

        try {
            scheduler.start();
            logger.info("✅ Scheduler démarré");

            // Lancer un enregistrement immédiatement
            logger.info("🎬 Lancement d'un enregistrement de test...");
            scheduler.triggerNow();

            // Attendre que l'enregistrement se termine (40 secondes pour être sûr)
            logger.info("⏳ Attente de la fin de l'enregistrement (40 secondes)...");
            Thread.sleep(40000);

            logger.info("✅ Test terminé - Vérifiez le dossier ./recordings");

            scheduler.stop();

        } catch (Exception e) {
            logger.error("❌ Erreur pendant le test", e);
            System.exit(1);
        }
    }*/

    private static boolean checkFFmpeg() {
        try {
            logger.info("Vérification de ffmpeg...");
            Process process = new ProcessBuilder("ffmpeg", "-version").start();
            int exitCode = process.waitFor();

            if (exitCode == 0) {
                logger.info("✅ ffmpeg est installé");
                return true;
            } else {
                logger.error("❌ ffmpeg retourne un code d'erreur: {}", exitCode);
                return false;
            }
        } catch (Exception e) {
            logger.error("❌ Impossible d'exécuter ffmpeg: {}", e.getMessage());
            return false;
        }
    }

    private static boolean testCheckStreamAccess() {
        try {
            logger.info("Test d'accès au stream...");
            Process process = new ProcessBuilder(
                    "ffmpeg",
                    "-i", "http://icecast.radiofrance.fr/franceinter-hifi.aac",
                    "-t", "1",
                    "-f", "null",
                    "-"
            ).start();

            int exitCode = process.waitFor();

            if (exitCode == 0) {
                logger.info("✅ Stream accessible");
                return true;
            } else {
                logger.warn("⚠️ Problème d'accès au stream (code: {})", exitCode);
                return false;
            }
        } catch (Exception e) {
            logger.error("❌ Erreur lors du test du stream: {}", e.getMessage());
            return false;
        }
    }
}