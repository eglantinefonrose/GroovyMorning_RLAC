# Spécification Technique : IA Chronicle Segmenter (Python)

## 1. Vue d'ensemble
Le service **IA Chronicle Segmenter** est un composant critique du système *GroovyMorning*. Son rôle est de détecter en temps réel le début et la fin des chroniques radio (principalement France Inter) en analysant le flux audio via des techniques de traitement du signal classiques (jingles) ou de l'IA sémantique (DeepSeek).

- **Stack technique** : Python 3.12
- **Framework Web** : Flask avec Flask-SocketIO pour les notifications en temps réel.
- **Moteur de détection** : 
    - **Audio** : FFmpeg pour la capture, NumPy/SciPy pour le traitement du signal.
    - **Transcription** : OpenAI Whisper (via `faster-whisper`) ou Kyutai (STT).
    - **Analyse Sémantique** : API DeepSeek.
- **Point d'entrée** : `api-server.py` (démarre l'API et le planificateur de tâches).

## 2. Modèles de données
Le service utilise une base de données **SQLite** locale pour la persistance des événements détectés.

### Table : `master_chronicle_events`
Stocke les points de passage (début/fin) validés par le service.
- **Emplacement** : `data/master_events.db` (défini par `DB_PATH`).
- **Champs** :
    - `id` (INTEGER, PK) : Identifiant unique.
    - `chronicle_name` (TEXT) : Nom de la chronique (ex: "Le journal de 7h").
    - `event_type` (TEXT) : Type d'événement (`start` ou `end`).
    - `master_timestamp` (TEXT) : Timecode dans le flux maître (secondes écoulées ou ISO).
    - `confidence` (FLOAT) : Score de confiance de la détection (0.0 à 1.0).

## 3. Interfaces publiques

### API REST (Flask)
| Méthode | Chemin | Description |
| :--- | :--- | :--- |
| `POST` | `/api/updateSchedulerTime` | Met à jour l'heure de démarrage/arrêt automatique du segmenter. Paramètres : `hour`, `minute`. |
| `POST` | `/api/realChronicleStartTime` | Déclare le début d'une chronique. Enregistre en DB, émet en WebSocket et forwarde au backend Java. |
| `POST` | `/api/realChronicleEndTime` | Déclare la fin d'une chronique. Similaire au début, inclut `realDuration`. |
| `POST` | `/api/sync_offset` | Proxy vers le segmenter (port 8002) pour synchroniser un flux client via fingerprinting audio. |
| `GET` | `/api/chronicles` | Récupère la grille des programmes scrappée pour une date donnée (`?date=DD-MM-YYYY`). |
| `GET` | `/api/status` | Retourne l'état de santé du service. |

### WebSocket (SocketIO)
- **`chronicle_start`** : Émis lors d'une détection de début (données : `userId`, `nomDeChronique`, `masterTimestamp`).
- **`chronicle_end`** : Émis lors d'une détection de fin (données : `userId`, `nomDeChronique`, `realDuration`, `masterTimestamp`).

## 4. Règles métier

### Modes de détection (`DETECTION_MODE`)
1.  **Mode Legacy (Jingles + Keywords)** : 
    - Utilise la corrélation croisée (FFT) pour détecter des jingles audio pré-enregistrés (`assets/jingles_chroniques`).
    - Utilise Whisper pour détecter des mots-clés spécifiques dans la transcription.
2.  **Mode DeepSeek (IA Sémantique)** :
    - Transcrit le flux audio en continu.
    - Envoie les phrases à l'API DeepSeek avec un prompt spécifique pour distinguer un **lancement réel** d'un simple **teasing** (annonce d'une chronique à venir).
    - Valide la détection par rapport à la grille théorique récupérée dynamiquement via le scraper.

### Logique du Scheduler
- Le service `api-server.py` gère un thread de planification (`scheduler_loop`).
- Il lance le processus `src/live_radio_segmenter.py` à `START_TIME` et l'arrête à `END_TIME`.
- En mode simulation (`SIMU=true`), le segmenter écoute sur un pipe FIFO (`/tmp/audio_pipe`) au lieu du flux URL live.

### Forwarding (Synchronisation Backend)
Tous les événements de détection sont systématiquement envoyés au backend Java via un POST HTTP (`forward_to_java`). Cette opération est asynchrone (lancée dans un thread séparé) pour ne pas bloquer le traitement audio.

## 5. Dépendances externes
- **Backend Java** : Accessible via `JAVA_API_URL` (défaut: `http://localhost:8080`).
- **Flux Radio** : France Inter (`https://stream.radiofrance.fr/...`).
- **Scraping** : Site Radio France pour extraire la grille en temps réel (via `src/scraper.py`).
- **DeepSeek API** : Requis pour le mode `deepseek`.
- **Modèle Whisper** : Pré-chargé (`medium` par défaut) dans l'image Docker.

## 6. Contraintes non-fonctionnelles
- **Performance** : Latence ultra-faible recherchée (chunks de 32ms pour le traitement signal).
- **Concurrence** : Utilisation intensive de threads pour séparer la capture audio, la transcription et les appels API externes.
- **Robustesse** : Redémarrage automatique du processus de segmentation en cas de crash (via le scheduler).

## 7. Code mort / suspect

### Éléments morts (confirmés ou forte suspicion)
- **`scheduler.py`** (Racine) : **Mort**. Le code est désormais intégré directement dans `api-server.py`. Le script `entrypoint.sh` contient d'ailleurs un commentaire explicite à ce sujet (l. 17).
- **Dossiers `api/`, `core/`, `models/` (Racine)** : **Suspect**. Ces dossiers ne contiennent que des fichiers `.pyc` dans `__pycache__` mais aucun fichier `.py` source n'est présent. `api-server.py` n'importe rien de ces dossiers. Ils semblent être des restes d'une ancienne architecture (type FastAPI).
- **Route `/api/sync_offset`** (`api-server.py`, l. 189) : **Suspect**. La route tente de contacter `localhost:8002`, mais `live_radio_segmenter.py` ne lance aucun serveur HTTP sur ce port. Cette fonctionnalité semble incomplète ou obsolète.

### Éléments à vérifier
- **`src/transcriber.py`** : Supporte de nombreux providers (Kyutai, MLX, etc.) mais seul Whisper semble activement configuré via `requirements.txt` et le `Dockerfile`. Les autres providers pourraient être du code expérimental.
- **Variables `START_TIME` / `END_TIME`** : Codées en dur par défaut (`15:00` / `15:30`) dans le code si non fournies en variables d'environnement, ce qui peut surprendre pour une matinale radio.
