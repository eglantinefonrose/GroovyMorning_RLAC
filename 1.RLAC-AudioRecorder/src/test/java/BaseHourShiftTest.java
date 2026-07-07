import org.junit.jupiter.api.Test;
import recording.service.Chronicle;
import recording.service.ChroniclesManagerService;
import recording.service.RadioProgramService;
import service.DatabaseService;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class BaseHourShiftTest {

    @Test
    void testStartTimeShiftWithBaseHour6() {
        ChroniclesManagerService chroniclesManagerService = ChroniclesManagerService.getInstance();
        DatabaseService dbService = DatabaseService.getInstance();
        
        String userId = "user_base6_" + System.currentTimeMillis();
        
        // Configurer l'utilisateur à 6:00
        dbService.updateUserBaseTime(userId, 6, 0);
        
        // Récupérer les chroniques (devrait inclure les chroniques à partir de 6:00)
        // Les chroniques par défaut commencent à 7:00, donc elles devraient toutes être là,
        // mais avec un startTime de 3600 (7:00 - 6:00).
        List<Chronicle> chronicles = chroniclesManagerService.getChronicles(userId);
        
        assertFalse(chronicles.isEmpty());
        
        // Chercher "Le journal de 7h" (qui est à 0s de l'offset 7:00 interne)
        Chronicle journal7h = chronicles.stream()
                .filter(c -> c.getNomDeChronique().equals("Le journal de 7h"))
                .findFirst()
                .orElseThrow();
        
        // 7:00 AM relative to 6:00 AM should be 3600 seconds
        assertEquals(3600, journal7h.getStartTime(), "Le journal de 7h devrait commencer à 3600s de l'heure de base 6h00");
    }

    @Test
    void testChronicleAt6AMWithBaseHour6() {
        ChroniclesManagerService chroniclesManagerService = ChroniclesManagerService.getInstance();
        DatabaseService dbService = DatabaseService.getInstance();
        
        String userId = "user_base6_v2_" + System.currentTimeMillis();
        dbService.updateUserBaseTime(userId, 6, 0);
        
        // Ajouter une chronique qui commence à 6:00 AM (relative à 6:00 AM)
        // Via l'API interne, on simule l'ajout d'une chronique à 6:00 AM.
        // Puisqu'on utilise ChroniclesManagerService.addChronicle directement,
        // on doit fournir l'offset interne (relatif à 7:00 AM).
        // 6:00 AM est -3600s par rapport à 7:00 AM.
        Chronicle c6h = new Chronicle("Chronique de 6h", -3600, -3000);
        chroniclesManagerService.addChronicle(userId, c6h);
        
        List<Chronicle> chronicles = chroniclesManagerService.getChronicles(userId);
        
        Chronicle found = chronicles.stream()
                .filter(c -> c.getNomDeChronique().equals("Chronique de 6h"))
                .findFirst()
                .orElseThrow();
        
        assertEquals(0, found.getStartTime(), "Une chronique commençant à 6h00 devrait avoir un startTime de 0 si la baseHour est 6h00");
    }
}
