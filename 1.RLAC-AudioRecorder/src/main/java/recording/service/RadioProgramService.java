package recording.service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

public class RadioProgramService {

    private static final List<Chronicle> PROGRAM_CHRONICLES = new ArrayList<>();
    private static final Map<String, Chronicle> CHRONICLE_MAP;

    static {
        // Source: User request (updated default program)
        PROGRAM_CHRONICLES.add(new Chronicle("journal de 7h", 0, 780));
        PROGRAM_CHRONICLES.add(new Chronicle("les 80 secondes", 780, 960));
        PROGRAM_CHRONICLES.add(new Chronicle("Le grand reportage", 960, 1200));
        PROGRAM_CHRONICLES.add(new Chronicle("Edito media", 1200, 1380));
        PROGRAM_CHRONICLES.add(new Chronicle("Musicaline", 1380, 1680));
        PROGRAM_CHRONICLES.add(new Chronicle("Meteo", 1680, 1800));
        PROGRAM_CHRONICLES.add(new Chronicle("Le journal de 7h30", 1800, 2580));
        PROGRAM_CHRONICLES.add(new Chronicle("Edito politique", 2580, 2760));
        PROGRAM_CHRONICLES.add(new Chronicle("Edito eco", 2760, 3000));
        PROGRAM_CHRONICLES.add(new Chronicle("L’invite de 7h50", 2940, 3360));
        PROGRAM_CHRONICLES.add(new Chronicle("Billet de Bertrant Chameroy", 3360, 3600));
        PROGRAM_CHRONICLES.add(new Chronicle("Journal de 8h00", 3600, 4620));
        PROGRAM_CHRONICLES.add(new Chronicle("Geopolitique", 4620, 4800));

        CHRONICLE_MAP = PROGRAM_CHRONICLES.stream()
                .collect(Collectors.toMap(Chronicle::getNomDeChronique, Function.identity()));
    }

    public static List<Chronicle> getAllChronicles() {
        return new ArrayList<>(PROGRAM_CHRONICLES);
    }

    public static Chronicle getChronicleByName(String name) {
        return CHRONICLE_MAP.get(name);
    }
}
