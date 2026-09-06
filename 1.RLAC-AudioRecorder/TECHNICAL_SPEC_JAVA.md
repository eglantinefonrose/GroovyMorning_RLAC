# Spécification Technique : Serveur Java RLAC-AudioRecorder

Ce document détaille l'architecture et le fonctionnement du module **1.RLAC-AudioRecorder**, responsable de la capture du flux audio live, de la gestion des chroniques personnalisées et de la génération des segments HLS.

---

## 1. Vue d'ensemble

*   **Framework** : Java 21, application autonome utilisant **Jetty** comme serveur embarqué.
*   **Système de Build** : Gradle 8.x.
*   **Point d'entrée** : `org.example.api.RLACServerAPI`.
*   **Architecture** : Orientée services, basée sur des Singletons pour la gestion du matériel (FFmpeg) et des données (SQLite).
*   **Modules principaux** :
    *   `org.example.api` : Couche REST (Jersey/JAX-RS).
    *   `recording.service` : Logique de capture FFmpeg et ordonnancement Quartz.
    *   `service` : Services transverses (Database, WebSocket, RLAC Logic).

---

## 2. Modèles de données

*   **Chronicle** (`recording.service.Chronicle`) :
    *   `nomDeChronique` (String) : Identifiant lisible.
    *   `startTime` / `endTime` (Integer) : Offsets en secondes par rapport à une référence interne (07h00 par défaut).
*   **UserConfig** (`service.DatabaseService.UserConfig`) :
    *   `baseHour` / `baseMinute` : Heure de réveil de l'utilisateur (début de sa matinale personnalisée).
*   **Persistence** : SQLite (`data/rlac.db`).
    *   Tables : `users`, `user_chronicles`, `app_config` (stocke le `local_user_id`), `user_status`.

---

## 3. Interfaces publiques

### API REST (`/api`)
Le serveur expose une API REST sur le port `8000` (configurable via `SERVER_PORT`).

| Méthode | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/status` | État du serveur et chemin du répertoire média. |
| `GET` | `/findTodayFolder` | Retourne le dossier de session le plus récent pour l'utilisateur local. |
| `POST` | `/addChronicle` | Ajoute une chronique manuellement (params: `nomDeChroniques`, `chroniqueRealTimecode`, `duration`). |
| `GET` | `/getUserChronicles` | Récupère la liste des chroniques, synchronisée avec l'API Python. |
| `DELETE` | `/removeChronicles` | Supprime toutes les chroniques de l'utilisateur local. |
| `DELETE` | `/clearUserConfig` | Réinitialise complètement la configuration utilisateur. |
| `GET` | `/getUserBaseTime` | Récupère l'heure de base (`baseHour`, `baseMinute`). |
| `POST` | `/setUserBaseTime` | Met à jour l'heure de base et notifie le scheduler Python. |
| `POST` | `/realChronicleStartTime` | Notification de début de chronique (déclenche l'enregistrement FFmpeg). |
| `POST` | `/realChronicleEndTime` | Notification de fin de chronique (arrête l'enregistrement). |
| `POST` | `/ping` | Déclenche le flux continu FFmpeg s'il est arrêté. |
| `POST` | `/feedAudio` | Extrait et envoie un chunk audio de 1s à l'API Python pour analyse. |

### WebSocket (`WebSocketClientService`)
Le serveur se connecte en tant que client au serveur Python (`PYTHON_API_URL`).
*   **Événements écoutés** :
    *   `chronicle_start` : Déclenche `handleStartNotification` si la chronique est dans le planning utilisateur.
    *   `chronicle_end` : Déclenche `handleEndNotification`.

---

## 4. Règles métier

*   **Référence Temporelle** : Toutes les chroniques sont stockées avec un offset relatif à `REFERENCE_SECONDS` (07h00). L'affichage client est recalculé en fonction de l'heure de base de l'utilisateur.
*   **Enregistrement Continu** : FFmpeg capture le flux AAC de France Inter en permanence (`media/continuous/`) par segments HLS de 1 seconde (`fmp4`).
*   **Découpage Dynamique** : Lors d'un `START`, le serveur commence à "lier" (hardlink) les segments du flux continu vers un dossier spécifique à la chronique. Au `END`, il finalise le manifeste `.m3u8`.
*   **Synchronisation Maître** (`Master Sync`) : Au démarrage, le serveur Java envoie une empreinte audio (fingerprint) au serveur Python pour calculer un offset précis (latence du flux) et synchroniser les timestamps.
*   **Gestion Multi-Utilisateurs** : Bien que conçu pour un "utilisateur local", le code supporte plusieurs `user_id` en base, mais les notifications WebSocket actuelles ciblent le `localUserId`.
*   **Nettoyage Automatique** : Un nettoyage quotidien est effectué 5 minutes avant l'heure de base de l'utilisateur pour vider `media/continuous/`.

---

## 5. Dépendances externes

*   **FFmpeg** : Indispensable pour la capture, le découpage et la génération HLS.
*   **SQLite** : Base de données locale.
*   **Python API** (`PYTHON_API_URL`) : Utilisé pour la synchronisation des chroniques, le master sync et le relayage des notifications via WebSocket.
*   **France Inter (Icecast)** : Source audio `http://icecast.radiofrance.fr/franceinter-hifi.aac`.
*   **Variables d'environnement** :
    *   `SERVER_PORT`, `SERVER_HOST`
    *   `DB_PATH` (défaut: `data/rlac.db`)
    *   `PYTHON_API_URL` (défaut: `http://localhost:8001`)
    *   `FFMPEG_PATH`
    *   `DISABLE_MASTER_SYNC` (booléen)

---

## 6. Contraintes non-fonctionnelles

*   **Performance** : Utilisation de Hardlinks (`java.nio.file.Files.createLink`) pour éviter la copie physique des fichiers audio lors du découpage des chroniques.
*   **Threading** :
    *   `ScheduledExecutorService` pour le nettoyage et les timeouts de sécurité.
    *   Fils dédiés pour chaque tâche d'enregistrement FFmpeg (`ChronicleRecordingTask`).
*   **Logging** : SLF4J avec Logback. Fichier de configuration `resources/logback.xml`.
*   **Sécurité** : Aucune authentification implémentée sur l'API REST (supposée être dans un réseau privé ou derrière un proxy).

---

## 7. Code mort / suspect

| Composant | Niveau de confiance | Preuve / Raison |
| :--- | :--- | :--- |
| `service.PlaylistService` | **Élevé** | Instancié dans `RLACServerAPI` mais jamais appelé. Les méthodes de concaténation AAC/MP3 semblent obsolètes face à l'approche HLS dynamique. |
| `recording.service.RecordingScheduler` (Quartz) | **Moyen** | Le code indique que les chroniques sont maintenant gérées dynamiquement. Les méthodes `scheduleAllUserChronicles` ne font plus que des logs. Quartz n'est utilisé que pour `cancelAllJobsForUser`. |
| `recording.service.ScheduleStorage` | **Moyen** | Gère un fichier `schedule.json` et des objets `ScheduleData`. Aucun endpoint REST ne semble l'alimenter. Semble être un reliquat d'une ancienne méthode d'ordonnancement fixe. |
| `api.dto.PlaylistRequest` | **Élevé** | Classe DTO présente mais jamais utilisée dans les signatures de méthodes de `RLACServerAPI`. |

---
*Document généré par Gemini CLI le 6 septembre 2026.*
