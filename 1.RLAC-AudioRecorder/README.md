
# RLAC Java Server


## Système de Programmation des Chroniques

Ce document décrit le fonctionnement du système de programmation et d'enregistrement des chroniques radio pour les utilisateurs.

### 1. Vue d'ensemble

Le système permet aux utilisateurs de programmer l'enregistrement de leurs chroniques favorites. Chaque chronique est définie par un nom, une heure de début et une heure de fin (en secondes depuis le début du programme). Le système utilise [Quartz Scheduler](https://www.quartz-scheduler.org/) pour planifier des jobs d'enregistrement qui, à leur tour, utilisent [FFmpeg](https://ffmpeg.org/) pour enregistrer le flux audio et le segmenter en fichiers M3U8.

### 2. Composants Clés

*   **`Chronicle.java`**:
    *   Représente une chronique avec son `nomDeChronique`, `startTime` (en secondes) et `endTime` (en secondes).

*   **`ChroniclesManagerService.java`**:
    *   Gère une collection de chroniques **par utilisateur**.
    *   Stocke les chroniques dans une `Map<String, List<Chronicle>>` où la clé est le `userID` et la valeur est la liste des chroniques associées à cet utilisateur.
    *   Méthodes principales :
        *   `addChronicle(String userID, Chronicle chronicle)`: Ajoute une chronique à la liste d'un utilisateur spécifié.
        *   `getChronicles(String userID)`: Récupère toutes les chroniques pour un utilisateur donné.

*   **`RecordingScheduler.java`**:
    *   Utilise Quartz pour planifier et gérer les jobs d'enregistrement.
    *   Méthodes principales :
        *   `start(String userID, Integer hour, Integer minute, Integer duration, String chronicleName, String folderName)`: Planifie un `RadioRecordingJob` unique à une heure et minute spécifiques, avec une durée, un nom de chronique et un nom de dossier optionnels.
        *   `scheduleChronicles(String userID, int baseHour, int baseMinute, List<Chronicle> chronicles)`: La méthode clé qui prend une liste de chroniques pour un utilisateur et les planifie séquentiellement. Elle calcule l'heure de début absolue de chaque chronique en ajoutant son `startTime` à une `baseHour` et `baseMinute` de référence, puis appelle `start` pour chaque chronique.

*   **`RadioRecordingJob.java`**:
    *   C'est un `org.quartz.Job` qui est exécuté par le `RecordingScheduler`.
    *   Contient la logique pour appeler FFmpeg.
    *   Récupère les données (`userID`, `chronicleName`, `hour`, `minute`, `duration`, `folderName`) du `JobDataMap` de Quartz.
    *   Crée un répertoire de sortie sous `media/userID_[userID]/[folderName]` ou `media/userID_[userID]/schedule_[timestamp]_[nomDeChronique]` si `folderName` n'est pas fourni.
    *   Exécute la commande FFmpeg pour enregistrer le flux audio (`STREAM_URL`) et le convertir en segments HLS (MP4) et une playlist M3U8.
    *   Le nom du fichier M3U8 et des segments HLS est basé sur le `chronicleName` fourni (ex: `nomDeChronique.m3u8`, `nomDeChronique_init.mp4`, `nomDeChronique_segment_000.m4s`).

*   **`RLACService.java`**:
    *   Fournit la logique métier générale.
    *   Injecte `RecordingScheduler` et `ChroniclesManagerService`.
    *   Méthode clé ajoutée : `scheduleAllUserChronicles(String userID, int baseHour, int baseMinute)`: Récupère toutes les chroniques pour l'utilisateur via `ChroniclesManagerService` et les passe à `RecordingScheduler.scheduleChronicles`.

*   **`RLACServerAPI.java`**:
    *   Le point d'entrée REST API du serveur (Jersey/Jetty).
    *   Instancie et injecte `RecordingScheduler`, `ChroniclesManagerService` et `RLACService`.
    *   Endpoints pertinents :
        *   `POST /api/addChronicle`: Permet d'ajouter une chronique spécifique à un utilisateur.
            *   Paramètres: `userId`, `nomDeChroniques`, `chroniqueRealTimecode` (startTime).
        *   `POST /api/scheduleAllUserChronicles`: Déclenche la programmation de **toutes** les chroniques associées à un `userId`.
            *   Paramètres: `userId`, `baseHour`, `baseMinute`. Les `baseHour` et `baseMinute` servent de point de départ pour calculer les heures de début réelles de chaque chronique.

### 3. Flux de Travail pour la Programmation des Chroniques

1.  **Ajout de chroniques à un utilisateur (optionnel)**: Un utilisateur peut ajouter des chroniques personnalisées via l'endpoint `POST /api/addChronicle`. Ces chroniques sont stockées dans `ChroniclesManagerService`.
2.  **Déclenchement de la programmation**: L'utilisateur appelle l'endpoint `POST /api/scheduleAllUserChronicles` avec son `userId`, une `baseHour` et une `baseMinute`.
3.  **Récupération des chroniques**: `RLACService` récupère la liste des chroniques pour cet `userId` depuis `ChroniclesManagerService`.
4.  **Planification des jobs**: `RLACService` passe cette liste à `RecordingScheduler.scheduleChronicles`.
5.  **Calcul des heures de début**: `RecordingScheduler` itère sur chaque chronique :
    *   Il calcule l'heure de début absolue de chaque chronique en ajoutant son `startTime` (offset en secondes) à la `baseHour` et `baseMinute` fournies.
    *   Il détermine la durée de l'enregistrement (`endTime - startTime`).
    *   Il génère un nom de dossier de session unique (`session_YYYYMMDD_HHmmss`) pour regrouper tous les enregistrements de cette session de planification.
6.  **Création et planification du Job Quartz**: Pour chaque chronique, un `JobDetail` de type `RadioRecordingJob` est créé et configuré avec les données de la chronique (userID, nomDeChronique, heure, minute, durée, nom du dossier de session). Un `CronTrigger` est créé pour déclencher le job à l'heure calculée.
7.  **Exécution du Job `RadioRecordingJob`**: À l'heure prévue, `RadioRecordingJob.execute()` est appelé :
    *   Il crée le répertoire `media/userID_[userID]/[sessionFolderName]`.
    *   Il construit et exécute la commande FFmpeg pour enregistrer le flux.
    *   Le fichier M3U8 et les segments HLS sont nommés en utilisant le `chronicleName` extrait du `JobDataMap`, assurant que `playlist.m3u8` et les fichiers `.mp4`/`.m4s` portent le nom de la chronique.
    *   Les enregistrements sont stockés dans le répertoire `media/userID_[userID]/[sessionFolderName]`.

### 4. Exemple d'utilisation

1.  **Ajouter des chroniques (si non déjà définies ou pour personnaliser)**:
    ```bash
    curl -X POST "http://localhost:8000/api/addChronicle?userId=testUser&nomDeChroniques=MonEmissionTest&chroniqueRealTimecode=0&endTime=600"
    curl -X POST "http://localhost:8000/api/addChronicle?userId=testUser&nomDeChroniques=MaSecondeChronique&chroniqueRealTimecode=600&endTime=1200"
    ```
    (Note: `endTime` n'est pas utilisé dans `addChronicle` pour l'instant, mais il est dans l'objet `Chronicle`.)

2.  **Programmer toutes les chroniques pour l'utilisateur `testUser` à partir de 7h00 du matin**:
    ```bash
    curl -X POST "http://localhost:8000/api/scheduleAllUserChronicles?userId=testUser&baseHour=7&baseMinute=0"
    ```

Ceci planifiera les enregistrements en respectant l'ordre et les durées définies dans les chroniques de l'utilisateur `testUser`, en commençant à 7h00. Chaque enregistrement sera nommé d'après la chronique correspondante.
