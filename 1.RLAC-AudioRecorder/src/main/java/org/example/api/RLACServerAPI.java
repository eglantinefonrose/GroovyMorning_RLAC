package org.example.api;

import jakarta.ws.rs.*;

import jakarta.ws.rs.core.MediaType;

import jakarta.ws.rs.core.Response;

import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.server.handler.HandlerList;

import org.eclipse.jetty.server.handler.ResourceHandler;

import org.eclipse.jetty.servlet.ServletContextHandler;

import org.eclipse.jetty.servlet.ServletHolder;

import org.glassfish.jersey.servlet.ServletContainer;

import org.quartz.SchedulerException;
import org.slf4j.Logger;

import org.slf4j.LoggerFactory;

import org.example.api.dto.PlaylistRequest;

import recording.service.*;

import service.DatabaseService;
import service.PlaylistService;
import service.RLACService;
import service.WebSocketClientService;

import java.io.File;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.*;

@Path("/api")


public class RLACServerAPI {


    public static final Logger logger = LoggerFactory.getLogger(RLACServerAPI.class);

    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("SERVER_PORT", "8000"));
    private static final String HOST = System.getenv().getOrDefault("SERVER_HOST", "0.0.0.0");

    private static final String MEDIA_DIR = "media";


        private final ChroniclesManagerService chroniclesManagerService;
        private final RecordingScheduler recordingScheduler;
        private final PlaylistService playlistService;
        private final RLACService rlacService;
        private final DynamicRecordingService dynamicRecordingService;
    
        public RLACServerAPI() throws SchedulerException {
            this.chroniclesManagerService = ChroniclesManagerService.getInstance();
            this.recordingScheduler = RecordingScheduler.getInstance();
            this.playlistService = new PlaylistService();
            this.rlacService = new RLACService(recordingScheduler, chroniclesManagerService);
            this.dynamicRecordingService = DynamicRecordingService.getInstance();
        }
    
        public static void main(String[] args) throws Exception {

        Server server = new Server();
        ServerConnector connector = new ServerConnector(server);
        connector.setHost(HOST);
        connector.setPort(PORT);
        server.addConnector(connector);

        ResourceHandler resourceHandler = new ResourceHandler();
        resourceHandler.setDirectoriesListed(true);
        resourceHandler.setWelcomeFiles(new String[]{"index.html"});
        File mediaDir = new File(MEDIA_DIR);
        resourceHandler.setResourceBase(mediaDir.getAbsolutePath());
        logger.info("Dossier média: " + mediaDir.getAbsolutePath());

        ServletContextHandler apiContext = new ServletContextHandler(ServletContextHandler.SESSIONS);
        apiContext.setContextPath("/");

        ServletHolder jerseyServlet = new ServletHolder(new ServletContainer());
        jerseyServlet.setInitParameter("jersey.config.server.provider.classnames", RLACServerAPI.class.getCanonicalName());
        apiContext.addServlet(jerseyServlet, "/*");
        HandlerList handlers = new HandlerList();
        handlers.addHandler(resourceHandler);
        handlers.addHandler(apiContext);
        server.setHandler(handlers);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Signal d'arrêt reçu");
            try {
                WebSocketClientService.getInstance().disconnect();
                DynamicRecordingService.getInstance().stopAll();
                RecordingScheduler.getInstance().shutdownScheduler();
                server.stop();
            } catch (Exception e) {
                logger.error("Erreur lors de l'arrêt", e);
            }
        }));

        WebSocketClientService.getInstance(); // Initialize WS connection
        DynamicRecordingService.getInstance(); // Initialize and trigger startup cleanup

        server.start();
        logger.info("========================================");
        logger.info("Serveur démarré sur http://" + HOST + ":" + PORT);
        logger.info("Fichiers statiques: http://" + HOST + ":" + PORT + "/");
        logger.info("API REST: http://" + HOST + ":" + PORT + "/api/...");
        logger.info("========================================");
        server.join();

    }

    /**

     * curl http://localhost:8000/api/status


     */


    @GET


    @Path("/status")


    @Produces(MediaType.APPLICATION_JSON)


    public Response getStatus() {


        Map<String, Object> status = new HashMap<>();


        status.put("status", "running");


        status.put("server", "MediaServer with Jersey");


        status.put("mediaDir", new File(MEDIA_DIR).getAbsolutePath());


        return Response.ok(status).build();


    }

    /**
     * curl "http://localhost:8000/api/findTodayFolder"
     */
    @GET
    @Path("/findTodayFolder")
    @Produces(MediaType.APPLICATION_JSON)
    public Response findTodayFolder() {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            Map<String, Object> result = RLACService.findTodayFolder(userId);
            result.put("status", "success");
            return Response.ok(result).build();
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("status", "error");
            error.put("message", e.getMessage());
            return Response.status(Response.Status.NOT_FOUND)
                    .entity(error)
                    .build();
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/addChronicle?nomDeChroniques=MaChronique&chroniqueRealTimecode=120&duration=300"
     */
    @POST
    @Path("/addChronicle")
    @Produces(MediaType.APPLICATION_JSON)
    public Response addChronicle(
            @QueryParam("nomDeChroniques") String nomDeChronique,
            @QueryParam("chroniqueRealTimecode") Integer chroniqueRealTimecode,
            @QueryParam("duration") Integer duration) {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            if (nomDeChronique == null || nomDeChronique.trim().isEmpty()) {
                return createErrorResponse("Le nom de la chronique ne peut pas être vide.");
            }
            if (chroniqueRealTimecode == null) {
                return createErrorResponse("Le realTimecode de la chronique ne peut pas être nul.");
            }

            // Le chroniqueRealTimecode fourni est relatif à l'heure de base de l'utilisateur.
            // On le convertit en offset relatif à REFERENCE_SECONDS (07h00) pour le stockage interne.
            DatabaseService.UserConfig config = DatabaseService.getInstance().getUserConfig(userId);
            int userBaseSeconds = config.baseHour * 3600 + config.baseMinute * 60;
            int storageStartTime = (userBaseSeconds + chroniqueRealTimecode) - ChroniclesManagerService.REFERENCE_SECONDS;

            int effectiveDuration = (duration != null) ? duration : 300; // 5 minutes par défaut
            Chronicle chronicle = new Chronicle(nomDeChronique, storageStartTime, storageStartTime + effectiveDuration);
                    
            chroniclesManagerService.addChronicle(userId, chronicle);
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Chronique ajoutée avec succès.");
            response.put("chronicle", Map.of(
                    "nomDeChronique", chronicle.getNomDeChronique(),
                    "startTimeRelativeToBase", chroniqueRealTimecode,
                    "startTimeInternal", chronicle.getStartTime(),
                    "endTimeInternal", chronicle.getEndTime()
            ));
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de l'ajout de la chronique", e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl "http://localhost:8000/api/getUserChronicles"
     */
    @GET
    @Path("/getUserChronicles")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getUserChronicles() {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            boolean updated = chroniclesManagerService.syncChroniclesWithExternalApi(userId);
            List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);

            Map<String, Object> response = new HashMap<>();
            response.put("chronicles", userChronicles);
            response.put("updated", updated);
            if (updated) {
                response.put("message", "La liste des chroniques a été mise à jour pour correspondre à la grille du jour.");
            }

            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la récupération des chroniques", e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl -X DELETE "http://localhost:8000/api/removeChronicles"
     */
    @DELETE
    @Path("/removeChronicles")
    @Produces(MediaType.APPLICATION_JSON)
    public Response removeUserChronicles() {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            logger.info("🗑️ Demande de suppression des chroniques pour l'utilisateur local: {}", userId);
            
            rlacService.removeUserChronicles(userId);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Toutes les chroniques ont été supprimées.");
            
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la suppression des chroniques", e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl -X DELETE "http://localhost:8000/api/clearUserConfig"
     */
    @DELETE
    @Path("/clearUserConfig")
    @Produces(MediaType.APPLICATION_JSON)
    public Response clearUserConfig() {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            logger.info("🧹 Demande de nettoyage complet de la configuration pour l'utilisateur: {}", userId);
            
            rlacService.clearUserConfiguration(userId);
            
            // Revenir à l'heure par défaut (07:00) pour le scheduler Python
            notifyPythonScheduler(7, 0);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "La liste des chroniques et l'heure de programmation ont été supprimées (remises à zéro).");
            
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors du nettoyage de la configuration", e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl "http://localhost:8000/api/getUserBaseTime"
     */
    @GET
    @Path("/getUserBaseTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getUserBaseTime() {
        String userId = DatabaseService.getInstance().getLocalUserId();
        try {
            DatabaseService.UserConfig config = DatabaseService.getInstance().getUserConfig(userId);
            Map<String, Object> response = new HashMap<>();
            response.put("userId", userId);
            response.put("baseHour", config.baseHour);
            response.put("baseMinute", config.baseMinute);
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la récupération de l'heure de base", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/setUserBaseTime?baseHour=8&baseMinute=30"
     */
    @POST
    @Path("/setUserBaseTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response setUserBaseTime(
            @QueryParam("baseHour") int baseHour,
            @QueryParam("baseMinute") int baseMinute) {

        String userId = DatabaseService.getInstance().getLocalUserId();
        if (baseHour < 0 || baseHour > 23 || baseMinute < 0 || baseMinute > 59) {
            return createErrorResponse("Heure ou minute invalide.");
        }

        try {
            DatabaseService.getInstance().updateUserBaseTime(userId, baseHour, baseMinute);
            
            // Notification au scheduler Python
            notifyPythonScheduler(baseHour, baseMinute);

            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Heure de base mise à jour : " + String.format("%02d:%02d", baseHour, baseMinute));
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la mise à jour de l'heure de base", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * Notifie le segmenter Python pour mettre à jour son scheduler
     */
    private void notifyPythonScheduler(int hour, int minute) {
        String pythonApiUrl = System.getenv().getOrDefault("PYTHON_API_URL", "http://localhost:8001");
        String url = pythonApiUrl + "/api/updateSchedulerTime?hour=" + hour + "&minute=" + minute;
        
        logger.info("Notification du scheduler Python à l'URL : {}", url);
        
        try (HttpClient client = HttpClient.newHttpClient()) {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .POST(HttpRequest.BodyPublishers.noBody())
                    .build();
            
            client.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                    .thenAccept(response -> {
                        if (response.statusCode() == 200) {
                            logger.info("Scheduler Python mis à jour avec succès : {}", response.body());
                        } else {
                            logger.warn("Échec de la mise à jour du scheduler Python. Status code : {}", response.statusCode());
                        }
                    })
                    .exceptionally(ex -> {
                        logger.error("Erreur lors de la notification du scheduler Python", ex);
                        return null;
                    });
        } catch (Exception e) {
            logger.error("Erreur lors de la création du client HTTP pour notifier Python", e);
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/realChronicleStartTime?nomDeChronique=MaChronique&deltaStartTimeInSeconds=10"
     */
    @POST
    @Path("/realChronicleStartTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response realChronicleStartTime(
            @QueryParam("nomDeChronique") String nomDeChronique,
            @QueryParam("deltaStartTimeInSeconds") Integer deltaStartTimeInSeconds) {
        
        String userId = DatabaseService.getInstance().getLocalUserId();
        logger.info("Notification START: localUserId={}, chronicle={}, delta={}", userId, nomDeChronique, deltaStartTimeInSeconds);
        
        if (nomDeChronique == null) {
            return createErrorResponse("Paramètre manquant (nomDeChronique)");
        }

        // Vérification que la chronique appartient à l'utilisateur local
        List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
        boolean exists = userChronicles.stream()
                .anyMatch(c -> c.getNomDeChronique().equals(nomDeChronique));
        
        if (!exists) {
            logger.warn("Tentative de démarrage d'une chronique non autorisée: {} pour l'utilisateur local {}", nomDeChronique, userId);
            return createErrorResponse("La chronique '" + nomDeChronique + "' n'est pas autorisée.");
        }

        try {
            dynamicRecordingService.handleStartNotification(userId, nomDeChronique, deltaStartTimeInSeconds);
            return Response.ok(Map.of("status", "success", "message", "Start notification processed")).build();
        } catch (Exception e) {
            logger.error("Erreur notification START", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/realChronicleEndTime?nomDeChronique=MaChronique&realDuration=realDuration"
     */
    @POST
    @Path("/realChronicleEndTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response realChronicleEndTime(
            @QueryParam("nomDeChronique") String nomDeChronique,
            @QueryParam("realDuration") String realDuration) {
        
        String userId = DatabaseService.getInstance().getLocalUserId();
        logger.info("Notification END: localUserId={}, chronicle={}, realDuration={}", userId, nomDeChronique, realDuration);
        
        if (nomDeChronique == null) {
            return createErrorResponse("Paramètre manquant (nomDeChronique)");
        }

        // Vérification que la chronique appartient à l'utilisateur local
        List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
        boolean exists = userChronicles.stream()
                .anyMatch(c -> c.getNomDeChronique().equals(nomDeChronique));
        
        if (!exists) {
            logger.warn("Tentative de fin d'une chronique non autorisée: {} pour l'utilisateur local {}", nomDeChronique, userId);
            return createErrorResponse("La chronique '" + nomDeChronique + "' n'est pas autorisée.");
        }

        try {
            dynamicRecordingService.handleEndNotification(userId, nomDeChronique, realDuration);
            return Response.ok(Map.of("status", "success", "message", "End notification processed")).build();
        } catch (Exception e) {
            logger.error("Erreur notification END", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/ping"
     */
    @POST
    @Path("/ping")
    @Produces(MediaType.APPLICATION_JSON)
    public Response ping() {
        logger.info("Ping received: starting continuous flow if not already running.");
        try {
            DynamicRecordingService.getInstance().getFFmpegService().startContinuousRecording();
            return Response.ok(Map.of("status", "success", "message", "Continuous flow active")).build();
        } catch (Exception e) {
            logger.error("Error during ping/start flow", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/feedAudio?positionInSeconds=2"
     */
    @POST
    @Path("/feedAudio")
    @Produces(MediaType.APPLICATION_JSON)
    public Response feedAudio(@QueryParam("positionInSeconds") Integer positionInSeconds) {
        if (positionInSeconds == null) {
            return createErrorResponse("Paramètre 'positionInSeconds' requis");
        }
        
        try {
            // Utiliser FFmpegService pour extraire et envoyer le chunk
            DynamicRecordingService.getInstance().getFFmpegService().extractAndSendChunk(positionInSeconds);
            return Response.ok(Map.of("status", "success", "message", "Chunk extraction and send triggered")).build();
        } catch (Exception e) {
            logger.error("Erreur lors de l'extraction/envoi du chunk", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    private Response createErrorResponse(String message) {
        Map<String, String> error = new HashMap<>();
        error.put("error", message);
        return Response.status(Response.Status.BAD_REQUEST)
                .entity(error)
                .build();
    }


}
