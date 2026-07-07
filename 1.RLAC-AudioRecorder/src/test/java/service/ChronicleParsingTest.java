package service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import recording.service.Chronicle;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class ChronicleParsingTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    public void testParseChronicleJson() throws Exception {
        String json = "[\n" +
                "  {\n" +
                "    \"time\": \"07:00\",\n" +
                "    \"title\": \"Le journal de 7h\"\n" +
                "  },\n" +
                "  {\n" +
                "    \"time\": \"07:16\",\n" +
                "    \"title\": \"Le grand reportage\"\n" +
                "  },\n" +
                "  {\n" +
                "    \"time\": \"07:24\",\n" +
                "    \"title\": \"La chronique de Xavier de La Porte\"\n" +
                "  }\n" +
                "]";

        List<Chronicle> chronicles = objectMapper.readValue(json, new TypeReference<List<Chronicle>>() {});

        assertEquals(3, chronicles.size());

        assertEquals("Le journal de 7h", chronicles.get(0).getNomDeChronique());
        assertEquals(0, chronicles.get(0).getStartTime());

        assertEquals("Le grand reportage", chronicles.get(1).getNomDeChronique());
        assertEquals(960, chronicles.get(1).getStartTime()); // (7*3600 + 16*60) - (7*3600) = 960

        assertEquals("La chronique de Xavier de La Porte", chronicles.get(2).getNomDeChronique());
        assertEquals(1440, chronicles.get(2).getStartTime()); // (7*3600 + 24*60) - (7*3600) = 1440
    }

    @Test
    public void testEndTimeCalculation() throws Exception {
        String json = "[\n" +
                "  {\n" +
                "    \"time\": \"07:00\",\n" +
                "    \"title\": \"C1\"\n" +
                "  },\n" +
                "  {\n" +
                "    \"time\": \"07:10\",\n" +
                "    \"title\": \"C2\"\n" +
                "  }\n" +
                "]";

        List<Chronicle> chronicles = objectMapper.readValue(json, new TypeReference<List<Chronicle>>() {});

        // Simuler la logique de ChroniclesManagerService
        for (int i = 0; i < chronicles.size(); i++) {
            Chronicle current = chronicles.get(i);
            if (i < chronicles.size() - 1) {
                current.setEndTime(chronicles.get(i + 1).getStartTime());
            } else {
                current.setEndTime(current.getStartTime() + 600);
            }
        }

        assertEquals(600, chronicles.get(0).getEndTime()); // 07:10 - 07:00 = 10 min = 600s
        assertEquals(600 + 600, chronicles.get(1).getEndTime()); // 07:10 + 10 min = 07:20 = 1200s offset from 07:00
    }
}
