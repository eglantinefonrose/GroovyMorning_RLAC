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
                    
                    String chronicleName = data.optString("nomDeChronique");
                    
                    // On utilise le localUserId pour la notification interne
                    String localUserId = DatabaseService.getInstance().getLocalUserId();
                    
                    // Vérification si cette chronique est dans MON planning
                    boolean isPlanned = DatabaseService.getInstance().getChronicles(localUserId).stream()
                            .anyMatch(c -> c.getNomDeChronique().equals(chronicleName));

                    if (isPlanned) {
                        logger.info("🎯 [User:{}] Chronicle {} is in my plan. Starting recording...", localUserId, chronicleName);
                        // L'offset est géré à l'intérieur de DynamicRecordingService via FFmpegService
                        DynamicRecordingService.getInstance().handleStartNotification(localUserId, chronicleName, null);
                    } else {
                        logger.debug("skipping chronicle {} (not in my plan)", chronicleName);
                    }
                } catch (Exception e) {
                    logger.error("Error processing chronicle_start event", e);
                }
            });

            socket.on("chronicle_end", args -> {
                try {
                    JSONObject data = (JSONObject) args[0];
                    logger.info("📥 WebSocket event: chronicle_end -> {}", data);
                    
                    String chronicleName = data.optString("nomDeChronique");
                    String realDuration = data.optString("realDuration");
                    String localUserId = DatabaseService.getInstance().getLocalUserId();

                    // On ne stop que si on est en train d'enregistrer
                    DynamicRecordingService.getInstance().handleEndNotification(localUserId, chronicleName, realDuration);
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
