package service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import recording.service.Chronicle;

import java.sql.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class DatabaseService {
    private static final Logger logger = LoggerFactory.getLogger(DatabaseService.class);
    private static final String DB_URL = "jdbc:sqlite:" + System.getenv().getOrDefault("DB_PATH", "data/rlac.db");
    private static DatabaseService instance;

    private DatabaseService() {
        initDatabase();
    }

    public static synchronized DatabaseService getInstance() {
        if (instance == null) {
            instance = new DatabaseService();
        }
        return instance;
    }

    private void initDatabase() {
        String createConfigTableSQL = "CREATE TABLE IF NOT EXISTS app_config (" +
                "key TEXT PRIMARY KEY," +
                "value TEXT" +
                ");";

        String createUsersTableSQL = "CREATE TABLE IF NOT EXISTS users (" +
                "user_id TEXT PRIMARY KEY," +
                "username TEXT," +
                "base_hour INTEGER DEFAULT 7," +
                "base_minute INTEGER DEFAULT 0" +
                ");";

        String createTableSQL = "CREATE TABLE IF NOT EXISTS user_chronicles (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "user_id TEXT NOT NULL," +
                "chronicle_name TEXT NOT NULL," +
                "start_time INTEGER NOT NULL," +
                "end_time INTEGER NOT NULL," +
                "play_order INTEGER NOT NULL," +
                "FOREIGN KEY(user_id) REFERENCES users(user_id)" +
                ");";

        String createStatusTableSQL = "CREATE TABLE IF NOT EXISTS user_status (" +
                "user_id TEXT PRIMARY KEY," +
                "has_custom_list BOOLEAN NOT NULL" +
                ");";

        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement()) {
            stmt.execute(createConfigTableSQL);
            stmt.execute(createUsersTableSQL);
            
            // Migration for existing databases
            try {
                stmt.execute("ALTER TABLE users ADD COLUMN base_hour INTEGER DEFAULT 7");
                stmt.execute("ALTER TABLE users ADD COLUMN base_minute INTEGER DEFAULT 0");
            } catch (SQLException e) {
                // Columns might already exist
            }

            stmt.execute(createTableSQL);
            stmt.execute(createStatusTableSQL);
            logger.info("Base de données SQLite initialisée à l'emplacement : {}", DB_URL);
            
            // Initialiser le localUserId s'il n'existe pas
            ensureLocalUserId();
            
            // Migration automatique de testUser vers le nouvel ID si nécessaire
            migrateFromTestUser();
        } catch (SQLException e) {
            logger.error("Erreur lors de l'initialisation de la base de données", e);
        }
    }

    private void migrateFromTestUser() {
        String localId = getLocalUserId();
        if ("testUser".equals(localId)) return;

        try (Connection conn = DriverManager.getConnection(DB_URL)) {
            // Vérifier si testUser a des chroniques et si localId n'en a pas
            boolean testUserHasData = false;
            boolean localIdHasData = false;

            try (PreparedStatement ps = conn.prepareStatement("SELECT count(*) FROM user_chronicles WHERE user_id = ?")) {
                ps.setString(1, "testUser");
                ResultSet rs = ps.executeQuery();
                if (rs.next()) testUserHasData = rs.getInt(1) > 0;

                ps.setString(1, localId);
                rs = ps.executeQuery();
                if (rs.next()) localIdHasData = rs.getInt(1) > 0;
            }

            if (testUserHasData && !localIdHasData) {
                logger.info("Migrating chronicles from 'testUser' to new localId '{}'", localId);
                
                // Copier les chroniques
                try (PreparedStatement ps = conn.prepareStatement(
                        "UPDATE user_chronicles SET user_id = ? WHERE user_id = 'testUser'")) {
                    ps.setString(1, localId);
                    ps.executeUpdate();
                }
                
                // Copier la config utilisateur
                try (PreparedStatement ps = conn.prepareStatement(
                        "INSERT OR IGNORE INTO users (user_id, username, base_hour, base_minute) " +
                        "SELECT ?, username, base_hour, base_minute FROM users WHERE user_id = 'testUser'")) {
                    ps.setString(1, localId);
                    ps.executeUpdate();
                }
            }
        } catch (SQLException e) {
            logger.error("Error during migration from testUser", e);
        }
    }

    private void ensureLocalUserId() {
        String checkSQL = "SELECT value FROM app_config WHERE key = 'local_user_id'";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(checkSQL)) {
            if (!rs.next()) {
                String newId = "user_" + java.util.UUID.randomUUID().toString().substring(0, 8);
                String insertSQL = "INSERT INTO app_config(key, value) VALUES('local_user_id', ?)";
                try (PreparedStatement pstmt = conn.prepareStatement(insertSQL)) {
                    pstmt.setString(1, newId);
                    pstmt.executeUpdate();
                    logger.info("Generated new localUserId: {}", newId);
                }
            }
        } catch (SQLException e) {
            logger.error("Error ensuring localUserId", e);
        }
    }

    public String getLocalUserId() {
        String querySQL = "SELECT value FROM app_config WHERE key = 'local_user_id'";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(querySQL)) {
            if (rs.next()) {
                return rs.getString("value");
            }
        } catch (SQLException e) {
            logger.error("Error retrieving localUserId", e);
        }
        return "unknown_user";
    }

    public void addUser(String userId, String username) {
        String sql = "INSERT OR IGNORE INTO users(user_id, username, base_hour, base_minute) VALUES(?,?,?,?)";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, userId);
            pstmt.setString(2, username);
            pstmt.setInt(3, 7); // Default hour
            pstmt.setInt(4, 0); // Default minute
            pstmt.executeUpdate();
        } catch (SQLException e) {
            logger.error("Erreur lors de l'ajout de l'utilisateur {}", userId, e);
        }
    }

    public void updateUserBaseTime(String userId, int hour, int minute) {
        String sql = "INSERT INTO users(user_id, base_hour, base_minute) VALUES(?,?,?) " +
                "ON CONFLICT(user_id) DO UPDATE SET base_hour=excluded.base_hour, base_minute=excluded.base_minute";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, userId);
            pstmt.setInt(2, hour);
            pstmt.setInt(3, minute);
            pstmt.executeUpdate();
            logger.info("Base time upserted for user {}: {}:{}", userId, hour, minute);
        } catch (SQLException e) {
            logger.error("Erreur lors de la mise à jour du base time pour l'utilisateur {}", userId, e);
        }
    }

    public UserConfig getUserConfig(String userId) {
        String querySQL = "SELECT base_hour, base_minute FROM users WHERE user_id = ?";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(querySQL)) {
            pstmt.setString(1, userId);
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                logger.info("Infos sur le user récupérées");
                System.out.println(rs.getInt("base_hour"));
                System.out.println(rs.getInt("base_minute"));
                return new UserConfig(rs.getInt("base_hour"), rs.getInt("base_minute"));
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la récupération de la config pour l'utilisateur {}", userId, e);
        }
        return new UserConfig(10, 10); // Default values
    }

    public static class UserConfig {
        public final int baseHour;
        public final int baseMinute;

        public UserConfig(int baseHour, int baseMinute) {
            this.baseHour = baseHour;
            this.baseMinute = baseMinute;
        }
    }

    public void addChronicle(String userId, Chronicle chronicle, int order) {
        String insertSQL = "INSERT INTO user_chronicles(user_id, chronicle_name, start_time, end_time, play_order) VALUES(?,?,?,?,?)";

        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(insertSQL)) {
            pstmt.setString(1, userId);
            pstmt.setString(2, chronicle.getNomDeChronique());
            pstmt.setInt(3, chronicle.getStartTime());
            pstmt.setInt(4, chronicle.getEndTime());
            pstmt.setInt(5, order);
            pstmt.executeUpdate();
        } catch (SQLException e) {
            logger.error("Erreur lors de l'ajout d'une chronique pour l'utilisateur {}", userId, e);
        }
    }

    public List<Chronicle> getChronicles(String userId) {
        List<Chronicle> chronicles = new ArrayList<>();
        String querySQL = "SELECT chronicle_name, start_time, end_time FROM user_chronicles WHERE user_id = ? ORDER BY play_order ASC";

        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(querySQL)) {
            pstmt.setString(1, userId);
            ResultSet rs = pstmt.executeQuery();

            while (rs.next()) {
                chronicles.add(new Chronicle(
                        rs.getString("chronicle_name"),
                        rs.getInt("start_time"),
                        rs.getInt("end_time")
                ));
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la récupération des chroniques pour l'utilisateur {}", userId, e);
        }
        return chronicles;
    }

    public void removeChroniclesForUser(String userId) {
        String deleteSQL = "DELETE FROM user_chronicles WHERE user_id = ?";

        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(deleteSQL)) {
            pstmt.setString(1, userId);
            pstmt.executeUpdate();
            logger.info("Toutes les chroniques pour l'utilisateur {} ont été supprimées de la base de données.", userId);
        } catch (SQLException e) {
            logger.error("Erreur lors de la suppression des chroniques pour l'utilisateur {}", userId, e);
        }
    }

    public Map<String, List<Chronicle>> getAllUserChronicles() {
        Map<String, List<Chronicle>> allChronicles = new HashMap<>();
        String querySQL = "SELECT user_id, chronicle_name, start_time, end_time FROM user_chronicles ORDER BY user_id, play_order ASC";

        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(querySQL)) {

            while (rs.next()) {
                String userId = rs.getString("user_id");
                Chronicle chronicle = new Chronicle(
                        rs.getString("chronicle_name"),
                        rs.getInt("start_time"),
                        rs.getInt("end_time")
                );
                allChronicles.computeIfAbsent(userId, k -> new ArrayList<>()).add(chronicle);
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la récupération de toutes les chroniques", e);
        }
        return allChronicles;
    }

    public boolean hasUserChronicles(String userId) {
        String querySQL = "SELECT count(*) FROM user_chronicles WHERE user_id = ?";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(querySQL)) {
            pstmt.setString(1, userId);
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                return rs.getInt(1) > 0;
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la vérification de l'existence de l'utilisateur {}", userId, e);
        }
        return false;
    }

    public void setUserHasCustomList(String userId, boolean hasCustomList) {
        String upsertSQL = "INSERT INTO user_status(user_id, has_custom_list) VALUES(?,?) " +
                "ON CONFLICT(user_id) DO UPDATE SET has_custom_list=excluded.has_custom_list";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(upsertSQL)) {
            pstmt.setString(1, userId);
            pstmt.setBoolean(2, hasCustomList);
            pstmt.executeUpdate();
        } catch (SQLException e) {
            logger.error("Erreur lors de la mise à jour du statut pour l'utilisateur {}", userId, e);
        }
    }

    public boolean hasUserCustomList(String userId) {
        String querySQL = "SELECT has_custom_list FROM user_status WHERE user_id = ?";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             PreparedStatement pstmt = conn.prepareStatement(querySQL)) {
            pstmt.setString(1, userId);
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                return rs.getBoolean("has_custom_list");
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la récupération du statut pour l'utilisateur {}", userId, e);
        }
        return false;
    }

    public List<String> getAllUsersWithCustomLists() {
        List<String> userIds = new ArrayList<>();
        String querySQL = "SELECT user_id FROM user_status WHERE has_custom_list = 1";
        try (Connection conn = DriverManager.getConnection(DB_URL);
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(querySQL)) {
            while (rs.next()) {
                userIds.add(rs.getString("user_id"));
            }
        } catch (SQLException e) {
            logger.error("Erreur lors de la récupération des utilisateurs avec listes personnalisées", e);
        }
        return userIds;
    }
}
