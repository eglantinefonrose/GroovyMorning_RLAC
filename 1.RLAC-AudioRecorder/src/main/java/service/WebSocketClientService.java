package service;

import io.socket.client.IO;
import io.socket.client.Socket;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import recording.service.DynamicRecordingService;

import java.net.URI;
import java.util.Collections;

public class WebSocketClientService {
    private static final Logger logger = LoggerFactory.getLogger(WebSocketClientService.class);
    private static WebSocketClientService instance;
    private Socket socket;
    private final String pythonApiUrl;

    private WebSocketClientService() {
        this.pythonApiUrl = System.getenv().getOrDefault("PYTHON_API_URL", "http://localhost:8001");
        initializeSocket();
    }

    public static synchronized WebSocketClientService getInstance() {
        if (instance == null) {
            instance = new WebSocketClientService();
        }
        return instance;
    }

    private void initializeSocket() {
        try {
            logger.info("🔌 Connecting to Python WebSocket at {}", pythonApiUrl);
            IO.Options options = IO.Options.builder()
                    .setForceNew(true)
                    .setReconnection(true)
                    .build();

            socket = IO.socket(URI.create(pythonApiUrl), options);

            socket.on(Socket.EVENT_CONNECT, args -> logger.info("✅ Connected to Python WebSocket"));
            socket.on(Socket.EVENT_DISCONNECT, args -> logger.warn("❌ Disconnected from Python WebSocket"));
            socket.on(Socket.EVENT_CONNECT_ERROR, args -> logger.error("⚠️ Connection error with Python WebSocket: {}", args[0]));

            socket.on("chronicle_start", args -> {
                try {
                    JSONObject data = (JSONObject) args[0];
                    logger.info("📥 WebSocket event: chronicle_start -> {}", data);
                    
                    String userId = data.optString("userId");
                    String chronicleName = data.optString("nomDeChronique");
                    Integer delta = data.has("deltaStartTimeInSeconds") && !data.isNull("deltaStartTimeInSeconds") ? 
                                    data.getInt("deltaStartTimeInSeconds") : null;

                    if (userId != null && chronicleName != null) {
                        DynamicRecordingService.getInstance().handleStartNotification(userId, chronicleName, delta);
                    }
                } catch (Exception e) {
                    logger.error("Error processing chronicle_start event", e);
                }
            });

            socket.on("chronicle_end", args -> {
                try {
                    JSONObject data = (JSONObject) args[0];
                    logger.info("📥 WebSocket event: chronicle_end -> {}", data);
                    
                    String userId = data.optString("userId");
                    String chronicleName = data.optString("nomDeChronique");
                    String realDuration = data.optString("realDuration");

                    if (userId != null && chronicleName != null) {
                        DynamicRecordingService.getInstance().handleEndNotification(userId, chronicleName, realDuration);
                    }
                } catch (Exception e) {
                    logger.error("Error processing chronicle_end event", e);
                }
            });

            socket.connect();
        } catch (Exception e) {
            logger.error("Failed to initialize WebSocket client", e);
        }
    }

    public void disconnect() {
        if (socket != null) {
            socket.disconnect();
        }
    }
}
