# Spécification d'Intégration - GroovyMorning (GMFM)

Ce document décrit les contrats d'échange, les flux de données et les mécanismes de sécurité entre les trois composants principaux du système GroovyMorning.

---

## 1. Carte des communications

Le système est composé de trois briques logicielles interagissant principalement via REST et WebSocket.

| Émetteur | Récepteur | Protocole | Rôle |
| :--- | :--- | :--- | :--- |
| **App Android** | **Backend Java** | REST (HTTP) | Configuration, Planning, Récupération des flux HLS |
| **Backend Java** | **Segmenter Python** | REST (HTTP) | Notification du scheduler, Synchronisation de la grille |
| **Backend Java** | **Segmenter Python** | WebSocket (Client) | Écoute passive des détections (Backup) |
| **Segmenter Python**| **Backend Java** | REST (HTTP) | Notification temps-réel des détections (Action) |
| **Segmenter Python**| **Backend Java** | WebSocket (Server)| Broadcast des détections |
| **Simu FFmpeg** | **Segmenter Python** | Pipe (FIFO) | Injection du flux audio en mode simulation |

### Topologie réseau (Docker Compose)
- **Java Backend** : `java-backend:8000`
- **Python Segmenter** : `python-segmenter:8001`
- **Android App** : Point d'entrée unique vers `java-backend`.

---

## 2. Contrats d'échange

### A. Flux Configuration (Android → Java → Python)
Le système utilise une heure de référence fixe à 07:00 pour la matinale de France Inter.
1.  **Configuration** : Plus de changement dynamique de l'heure de réveil par l'utilisateur.
2.  **Synchronisation** : Le Java et le Python se synchronisent sur l'heure de référence 07:00.

### B. Flux Détection (Python → Java)
Lorsqu'une chronique est détectée (Début ou Fin) :
1.  **Python → Java** (`POST /api/realChronicleStartTime`) ou (`POST /api/realChronicleEndTime`)
    - *Paramètres Start* : `nomDeChronique`, `startTime`, `confidence`, `userId`.
    - *Paramètres End* : `nomDeChronique`, `realDuration`, `endTime`, `userId`.
2.  **Broadcast WebSocket** (`chronicle_start` / `chronicle_end`)
    - *Format JSON* : `{"userId": "...", "nomDeChronique": "...", "masterTimestamp": "..."}`.

### C. Flux Synchronisation Grille (Java → Python)
Le Java rafraîchit sa liste de chroniques pour correspondre à la grille de France Inter :
1.  **Java → Python** (`GET /api/chronicles`)
    - *Réponse* : Liste JSON d'objets `Chronicle` (`nomDeChronique`, `startTime`).
2.  **Calcul interne Java** : Java calcule les `endTime` théoriques. Plus de filtrage par heure de base.

---

## 3. Authentification et Sécurité

Le système actuel est conçu pour un usage privé ou en réseau local restreint.

- **Authentification** : Aucune (pas de mot de passe, pas de JWT).
- **Identification** : Basée sur un `userId` statique envoyé en paramètre (`8dcb13c3` par défaut dans l'app Android).
- **Secrets** : Gérés via `.env` (API Keys DeepSeek) mais non partagés entre composants (seul Python en a besoin).
- **CORS** : Configuré en `*` sur le serveur Python pour faciliter le développement.

---

## 4. Parcours utilisateur critiques (Bout-en-bout)

### P1 : Initialisation de la matinale
1.  L'utilisateur ouvre l'app Android. Le système est déjà prêt pour la matinale commençant à **07:00**.
2.  **Java** est prêt avec les chroniques par défaut.
3.  **Python** est prêt pour la capture audio et l'analyse dès 07:00.
4.  À 07:00, **Python** lance le thread de capture audio et commence l'analyse.

### P2 : Détection et Enregistrement d'une chronique
1.  Le **Segmenter Python** détecte le jingle de "La revue de presse".
2.  Il envoie un `POST /realChronicleStartTime` au **Java**.
3.  Le **Java** vérifie que "La revue de presse" est dans le planning de l'utilisateur `8dcb13c3`.
4.  Le **Java** commence à lier (hardlink) les segments HLS du flux continu vers le dossier `/media/YYYY-MM-DD/La_revue_de_presse/`.
5.  Le **Java** met à jour le fichier `.m3u8` en temps réel.

### P3 : Écoute par l'utilisateur
1.  L'utilisateur clique sur "Play" sur "La revue de presse" dans l'app **Android**.
2.  L'app construit l'URL : `http://IP:8000/media/2026-09-06/La_revue_de_presse/La_revue_de_presse.m3u8`.
3.  **ExoPlayer** (Android) consomme les segments HLS servis par le serveur statique **Jetty** (Java).

---

## 5. Points de fragilité et Incohérences

### Incohérences détectées
- **Ports** : L'app Android a un port par défaut `8100` codé en dur dans le ViewModel, alors que le Java tourne sur `8000` et Python sur `8001`. Une reconfiguration manuelle de l'IP dans l'app est nécessaire.
- **UserId** : Le `userId` `8dcb13c3` est codé en dur dans de nombreux endroits (Android APIService, Android ViewModel). Le système n'est pas encore prêt pour un multi-utilisateur dynamique réel (bien que les bases DB soient présentes).
- **Redondance REST/WS** : Java écoute les signaux de Python via deux canaux. Si un canal est plus rapide que l'autre, des conditions de course pourraient apparaître (bien que `handleStartNotification` soit protégé contre les doublons).

### Fragilités
- **Couplage Fort** : Si le Java tombe, Python ne peut plus "forward" les signaux (timeout de 2s). Si Python tombe, Java ne peut plus synchroniser sa grille ni recevoir de détections.
- **Gestion du Temps** : Le décalage (offset) entre le flux Python (analyse) et le flux Java (enregistrement) est critique. Une dérive peut entraîner des débuts de chroniques tronqués.
- **Nettoyage** : Le nettoyage des médias est géré par Java (`DailyCleanupTask`). Si le serveur est éteint à ce moment, les fichiers s'accumulent.

---
*Document généré le 6 septembre 2026 par Gemini CLI.*
