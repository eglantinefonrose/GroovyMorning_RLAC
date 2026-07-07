package recording.service;

import org.junit.jupiter.api.Test;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class ChroniclesManagerServiceTest {

    private final ChroniclesManagerService service = new ChroniclesManagerService();

    @Test
    public void testAreChroniclesListsEqualIgnoringOrder() {
        Chronicle c1 = new Chronicle("Title 1", 100, 200);
        Chronicle c2 = new Chronicle("Title 2", 300, 400);
        Chronicle c3 = new Chronicle("Title 3", 500, 600);

        List<Chronicle> list1 = Arrays.asList(c1, c2, c3);
        List<Chronicle> list2 = Arrays.asList(c2, c3, c1);
        List<Chronicle> list3 = Arrays.asList(c3, c1, c2);

        assertTrue(service.areChroniclesListsEqual(list1, list2));
        assertTrue(service.areChroniclesListsEqual(list2, list3));
        assertTrue(service.areChroniclesListsEqual(list1, list3));
    }

    @Test
    public void testAreChroniclesListsDifferent() {
        Chronicle c1 = new Chronicle("Title 1", 100, 200);
        Chronicle c2 = new Chronicle("Title 2", 300, 400);
        
        List<Chronicle> list1 = Arrays.asList(c1, c2);
        
        // Different title
        List<Chronicle> list2 = Arrays.asList(c1, new Chronicle("Title X", 300, 400));
        assertFalse(service.areChroniclesListsEqual(list1, list2));

        // Different startTime
        List<Chronicle> list3 = Arrays.asList(c1, new Chronicle("Title 2", 350, 400));
        assertFalse(service.areChroniclesListsEqual(list1, list3));

        // Different endTime
        List<Chronicle> list4 = Arrays.asList(c1, new Chronicle("Title 2", 300, 450));
        assertFalse(service.areChroniclesListsEqual(list1, list4));

        // Different size
        List<Chronicle> list5 = Arrays.asList(c1);
        assertFalse(service.areChroniclesListsEqual(list1, list5));
    }

    @Test
    public void testNullLists() {
        assertTrue(service.areChroniclesListsEqual(null, null));
        assertFalse(service.areChroniclesListsEqual(null, Arrays.asList()));
        assertFalse(service.areChroniclesListsEqual(Arrays.asList(), null));
    }
}
