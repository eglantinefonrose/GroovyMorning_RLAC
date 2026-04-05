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
     * curl "http://localhost:8000/api/findTodayFolder?userId=testUser"
     */
    @GET
    @Path("/findTodayFolder")
    @Produces(MediaType.APPLICATION_JSON)
    public Response findTodayFolder(@QueryParam("userId") String userId) {

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
     * curl -X POST "http://localhost:8000/api/addChronicle?userId=testUser&nomDeChroniques=MaChronique&chroniqueRealTimecode=120&duration=300"
     */
    @POST
    @Path("/addChronicle")
    @Produces(MediaType.APPLICATION_JSON)
    public Response addChronicle(
            @QueryParam("userId") String userId,
            @QueryParam("nomDeChroniques") String nomDeChronique,
            @QueryParam("chroniqueRealTimecode") Integer chroniqueRealTimecode,
            @QueryParam("duration") Integer duration) {
        try {
            if (userId == null || userId.trim().isEmpty()) {
                return createErrorResponse("Le 'userId' est requis.");
            }
            if (nomDeChronique == null || nomDeChronique.trim().isEmpty()) {
                return createErrorResponse("Le nom de la chronique ne peut pas être vide.");
            }
            if (chroniqueRealTimecode == null) {
                return createErrorResponse("Le realTimecode de la chronique ne peut pas être nul.");
            }

            int effectiveDuration = (duration != null) ? duration : 300; // 5 minutes par défaut
            Chronicle chronicle = new Chronicle(nomDeChronique, chroniqueRealTimecode, chroniqueRealTimecode + effectiveDuration);
                    
            chroniclesManagerService.addChronicle(userId, chronicle);
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Chronique ajoutée avec succès pour l'utilisateur " + userId + ".");
            response.put("chronicle", Map.of(
                    "nomDeChronique", chronicle.getNomDeChronique(),
                    "startTime", chronicle.getStartTime(),
                    "endTime", chronicle.getEndTime()
            ));
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de l'ajout de la chronique", e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl "http://localhost:8000/api/getUserChronicles?userId=testUser"
     */
    @GET
    @Path("/getUserChronicles")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getUserChronicles(@QueryParam("userId") String userId) {
        if (userId == null || userId.trim().isEmpty()) {
            return createErrorResponse("Le \'userId\' est requis.");
        }
        try {
            List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
            return Response.ok(userChronicles).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la récupération des chroniques pour l'utilisateur " + userId, e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl -X DELETE "http://localhost:8000/api/removeChronicles?userId=testUser"
     */
    @DELETE
    @Path("/removeChronicles")
    @Produces(MediaType.APPLICATION_JSON)
    public Response removeUserChronicles(@QueryParam("userId") String userId) {
        if (userId == null || userId.trim().isEmpty()) {
            return createErrorResponse("Le 'userId' est requis.");
        }
        try {
            logger.info("🗑️ Demande de suppression des chroniques pour l'utilisateur: {}", userId);
            
            rlacService.removeUserChronicles(userId);
            
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Toutes les chroniques pour l'utilisateur " + userId + " ont été supprimées.");
            
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la suppression des chroniques pour l'utilisateur " + userId, e);
            return createErrorResponse("Erreur interne du serveur: " + e.getMessage());
        }
    }

    /**
     * curl "http://localhost:8000/api/getUserBaseTime?userId=testUser"
     */
    @GET
    @Path("/getUserBaseTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response getUserBaseTime(@QueryParam("userId") String userId) {
        if (userId == null || userId.trim().isEmpty()) {
            return createErrorResponse("Le 'userId' est requis.");
        }
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
     * curl -X POST "http://localhost:8000/api/setUserBaseTime?userId=testUser&baseHour=8&baseMinute=30"
     */
    @POST
    @Path("/setUserBaseTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response setUserBaseTime(
            @QueryParam("userId") String userId,
            @QueryParam("baseHour") int baseHour,
            @QueryParam("baseMinute") int baseMinute) {

        if (userId == null || userId.trim().isEmpty()) {
            return createErrorResponse("Le 'userId' est requis.");
        }
        if (baseHour < 0 || baseHour > 23 || baseMinute < 0 || baseMinute > 59) {
            return createErrorResponse("Heure ou minute invalide.");
        }

        try {
            DatabaseService.getInstance().updateUserBaseTime(userId, baseHour, baseMinute);
            Map<String, Object> response = new HashMap<>();
            response.put("status", "success");
            response.put("message", "Heure de base mise à jour pour " + userId + " : " + String.format("%02d:%02d", baseHour, baseMinute));
            return Response.ok(response).build();
        } catch (Exception e) {
            logger.error("Erreur lors de la mise à jour de l'heure de base", e);
            return createErrorResponse("Erreur: " + e.getMessage());
        }
    }

    /**
     * curl -X POST "http://localhost:8000/api/realChronicleStartTime?userId=testUser&nomDeChronique=MaChronique&deltaStartTimeInSeconds=10"
     */
    @POST
    @Path("/realChronicleStartTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response realChronicleStartTime(
            @QueryParam("userId") String userId,
            @QueryParam("nomDeChronique") String nomDeChronique,
            @QueryParam("deltaStartTimeInSeconds") Integer deltaStartTimeInSeconds) {
        
        logger.info("Notification START: userId={}, chronicle={}, delta={}", userId, nomDeChronique, deltaStartTimeInSeconds);
        
        if (userId == null || nomDeChronique == null) {
            return createErrorResponse("Paramètres manquants (userId, nomDeChronique)");
        }

        // Vérification que la chronique appartient à l'utilisateur
        List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
        boolean exists = userChronicles.stream()
                .anyMatch(c -> c.getNomDeChronique().equals(nomDeChronique));
        
        if (!exists) {
            logger.warn("Tentative de démarrage d'une chronique non autorisée: {} pour l'utilisateur {}", nomDeChronique, userId);
            return createErrorResponse("La chronique '" + nomDeChronique + "' n'est pas autorisée pour l'utilisateur " + userId);
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
     * curl -X POST "http://localhost:8000/api/realChronicleEndTime?userId=testUser&nomDeChronique=MaChronique&realDuration=realDuration"
     */
    @POST
    @Path("/realChronicleEndTime")
    @Produces(MediaType.APPLICATION_JSON)
    public Response realChronicleEndTime(
            @QueryParam("userId") String userId,
            @QueryParam("nomDeChronique") String nomDeChronique,
            @QueryParam("realDuration") String realDuration) {
        
        logger.info("Notification END: userId={}, chronicle={}, realDuration={}", userId, nomDeChronique, realDuration);
        
        if (userId == null || nomDeChronique == null) {
            return createErrorResponse("Paramètres manquants (userId, nomDeChronique)");
        }

        // Vérification que la chronique appartient à l'utilisateur
        List<Chronicle> userChronicles = chroniclesManagerService.getChronicles(userId);
        boolean exists = userChronicles.stream()
                .anyMatch(c -> c.getNomDeChronique().equals(nomDeChronique));
        
        if (!exists) {
            logger.warn("Tentative de fin d'une chronique non autorisée: {} pour l'utilisateur {}", nomDeChronique, userId);
            return createErrorResponse("La chronique '" + nomDeChronique + "' n'est pas autorisée pour l'utilisateur " + userId);
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
