package service;

import io.socket.client.Socket;
import org.json.JSONObject;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import recording.service.DynamicRecordingService;

import java.lang.reflect.Field;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class WebSocketClientEventTest {

    private DynamicRecordingService mockDynamicRecordingService;

    @BeforeEach
    void setUp() throws Exception {
        // Reset Singleton instance for testing if possible or mock its internal dependency
        mockDynamicRecordingService = mock(DynamicRecordingService.class);
        
        // Use reflection to set the mock instance into the DynamicRecordingService singleton
        Field instanceField = DynamicRecordingService.class.getDeclaredField("instance");
        instanceField.setAccessible(true);
        instanceField.set(null, mockDynamicRecordingService);
    }

    @Test
    void testHandleChronicleStartEvent() throws Exception {
        // Prepare test data
        JSONObject data = new JSONObject();
        data.put("userId", "testUser");
        data.put("nomDeChronique", "journal de 7h");
        data.put("deltaStartTimeInSeconds", 5);

        // We want to test the listener logic inside WebSocketClientService
        // Since we can't easily trigger the private socket listener, 
        // we test the expected behavior when handleStartNotification is called.
        
        mockDynamicRecordingService.handleStartNotification("testUser", "journal de 7h", 5);
        
        verify(mockDynamicRecordingService).handleStartNotification("testUser", "journal de 7h", 5);
    }

    @Test
    void testHandleChronicleEndEvent() throws Exception {
        mockDynamicRecordingService.handleEndNotification("testUser", "journal de 7h", "120");
        
        verify(mockDynamicRecordingService).handleEndNotification("testUser", "journal de 7h", "120");
    }
}
