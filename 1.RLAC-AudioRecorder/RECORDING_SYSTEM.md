# Système d'Enregistrement Dynamique (RLAC)

Ce document explique le fonctionnement du système d'enregistrement radio, qui est passé d'une planification statique (Quartz/Cron) à une gestion dynamique basée sur des notifications en temps réel.

## Architecture

Le système repose sur une collaboration entre un serveur de détection (Python) et ce serveur de gestion des médias (Java/Spring Boot).

1.  **Serveur Python** : Détecte les signaux audio et envoie les timecodes de début et de fin.
2.  **Serveur Java** : Reçoit les notifications, calcule l'heure réelle en fonction du décalage utilisateur, et pilote FFMPEG.

## Flux de données

### 1. Notification de début (`START`)
Lorsqu'une chronique commence, le serveur Python appelle :
`POST /api/realChronicleStartTime?userId=...&nomDeChronique=...&deltaStartTimeInSeconds=...`

*   **userId** : Identifiant de l'utilisateur.
*   **nomDeChronique** : Nom de la chronique (utilisé pour le dossier de sortie).
*   **deltaStartTimeInSeconds** (Optionnel) : Secondes écoulées depuis le début du flux global (buffer continu). Si présent, l'enregistrement commencera à ce décalage précis dans le buffer.

**Action Java** : 
- Calcule l'heure absolue : Si `deltaStartTimeInSeconds` est présent, utilise `Début Flux Continu + delta`. Sinon, utilise la fin de la chronique précédente ou l'heure actuelle.
- Crée une session d'enregistrement.
- Relie les segments du flux continu vers le dossier de la chronique.

### 2. Notification de fin (`END`)
Lorsqu'une chronique se termine, le serveur Python appelle :
`POST /api/realChronicleEndTime?userId=...&nomDeChronique=...&realDuration=...`

*   **userId** : Identifiant de l'utilisateur.
*   **nomDeChronique** : Nom de la chronique.
*   **realDuration** : Durée réelle de la chronique (ex: "10min30secondes" ou secondes).

**Action Java** : 
- Identifie la session active.
- Arrête le lien des segments.
- Finalise la playlist HLS (.m3u8).
- Déclenche automatiquement le début de la chronique suivante si elle existe dans le planning.

### 3. Extraction de chunk audio (`feedAudio`)
Permet d'extraire un segment de 1 seconde depuis le flux audio brut et de l'envoyer à un service externe.
`POST /api/feedAudio?positionInSeconds=...`

*   **positionInSeconds** : La position de départ de l'extraction dans le flux.

**Action Java** :
- Utilise FFmpeg pour extraire 1 seconde de `/tmp/audio_pipe_java` à partir de la position demandée.
- Envoie le fichier binaire résultant à `http://localhost:8001/api/feed_audio` via une commande `curl`.

### 4. Automatisation et Initialisation (`ping`)
Pour assurer que le flux continu est prêt et que le chunk de calage est envoyé *avant* le début des chroniques, l'endpoint `ping` peut être utilisé.
`POST /api/ping`

**Action Java** :
- Démarre le flux `Master` (enregistrement continu) s'il n'est pas déjà actif.
- **Extraction Automatique** : Dès que le flux commence, une tâche de fond attend la 3ème seconde de flux (`continuous_segment_00002.m4s`) et l'envoie automatiquement à l'API de destination (`localhost:8001`).

## Gestion des cas particuliers

| Cas | Solution |
| :--- | :--- |
| **Désordre** | Si le `END` arrive avant le `START`, la session est marquée comme "terminée" et l'enregistrement ne démarrera jamais pour cette instance. |
| **Notification manquante** | Un **Safety Timeout** de 1 heure est configuré. Si aucune notification de fin n'est reçue, l'enregistrement s'arrête automatiquement pour éviter de saturer le disque. |
| **Redémarrage** | Les processus FFMPEG sont liés au cycle de vie de l'application. En cas de crash, les enregistrements en cours sont interrompus. |
| **Calage précis** | L'utilisation de `deltaStartTimeInSeconds` permet de récupérer des segments déjà présents dans le buffer continu pour un calage parfait au début de la première chronique. |

## Configuration Utilisateur

Le système utilise la table `users` de la base de données SQLite pour récupérer le décalage (baseHour/baseMinute).

## Commandes de Test (CURL)

### Simuler un début de chronique avec décalage de 10s par rapport au début du flux
```bash
curl -X POST "http://localhost:8000/api/realChronicleStartTime?userId=testUser&nomDeChronique=Le_Billet_Humour&deltaStartTimeInSeconds=10"
```

### Simuler une fin de chronique
```bash
curl -X POST "http://localhost:8000/api/realChronicleEndTime?userId=testUser&nomDeChronique=Le_Billet_Humour&realDuration=300"
```

## Stockage des fichiers
Les fichiers sont organisés ainsi :
`media/userID_[ID]/session_[TIMESTAMP]/[NOM_CHRONIQUE]/[NOM_CHRONIQUE].m3u8`
