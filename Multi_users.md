# Architecture Multi-Utilisateurs Distribuée

Cette architecture permet de mutualiser l'intelligence de segmentation (IA) sur un serveur central tout en conservant la vie privée et la performance de l'enregistrement en local chez l'utilisateur.

## 1. Architecture du Serveur Central (Python)
Le serveur Python devient le "cerveau" du système. Il tourne en permanence sur une machine accessible par internet (Cloud/VPS).

*   **Exposition réseau :** Utilisation d'un Reverse Proxy (type **Nginx**) pour exposer les services via HTTPS.
    *   `https://api.groovymorning.com/` -> Redirige vers le port `8001` (API Métadonnées & WebSockets).
    *   `https://api.groovymorning.com/sync/` -> Redirige vers le port `8002` (API de synchronisation par fingerprint).
*   **Base de données Maître (SQLite) :** Un fichier `master_events.db` stocke les événements de segmentation "réels" détectés sur le flux de référence (ex: début de la chronique éco à 07:15:02).
*   **Mode "Broadcast" :** Le script `live_radio_segmenter.py` écoute le flux radio source une seule fois. Lorsqu'il détecte une chronique, il émet un événement WebSocket `chronicle_start` à **tous** les utilisateurs connectés.
*   **Agnosticisme :** Le serveur ne connaît pas les plannings des utilisateurs. Il diffuse simplement les événements de la radio en temps réel.

## 2. Architecture du Backend Local (Java)
Chaque utilisateur fait tourner son propre backend Java, agissant comme un agent local intelligent.

*   **Identité Unique :** Chaque instance génère un `local_user_id` (UUID) persistant, utilisé pour s'identifier auprès du serveur central.
*   **Planning Local :** L'utilisateur définit son propre planning de chroniques en local. Le Java filtre les messages WebSockets reçus : il n'enregistre que les chroniques présentes dans **son** planning.
*   **Enregistrement Local :** Utilisation de FFmpeg pour enregistrer le flux radio (Icecast) directement sur le stockage local (dossier `media/`). Qualité maximale garantie sans latence réseau.
*   **Base de données locale (SQLite) :** Le fichier `rlac.db` stocke les préférences, le planning et l'index des fichiers enregistrés de l'utilisateur.

## 3. Synchronisation par Fingerprinting (Le recalage)
Comme chaque flux radio (Icecast) a un délai de streaming différent (entre 2s et 30s de retard), le système utilise un mécanisme de synchronisation acoustique :

1.  **Génération de l'empreinte :** Au démarrage, le Java local extrait 2 secondes de son flux local et les compresse en une empreinte acoustique légère (4000Hz mono, ~16 Ko).
2.  **Envoi au serveur :** Cette empreinte est envoyée via `/api/sync_offset`.
3.  **Comparaison (Cross-Correlation) :** Le serveur Python compare l'empreinte reçue avec ses 60 dernières secondes de "mémoire tampon" du flux maître.
4.  **Calcul du Delta :** Le serveur renvoie un score de confiance et un `delta` (ex: "Ton flux a 4.5s de retard sur le mien").
5.  **Application du Delta :** Le Java local stocke ce `masterOffset`. Lorsqu'il reçoit un signal WebSocket de début de chronique, il ajuste ses points de découpe de 4.5s pour être parfaitement synchronisé.

## 4. Résumé des flux de données

| Composant | Rôle | Connexion | Données échangées |
| :--- | :--- | :--- | :--- |
| **Java Local** | Enregistrement | Sortant vers Icecast | Flux audio (AAC/MP3) |
| **Java Local** | Signalisation | WebSocket (entrant) | Événements JSON (Start/End) |
| **Java Local** | Synchronisation | HTTPS POST (sortant) | Fingerprint audio (16 Ko) |
| **Python Central** | Analyse IA | Entrant depuis Icecast | Flux audio maître |
| **Python Central** | Distribution | WebSocket (sortant) | Broadcast JSON vers tous les clients |
| **Python Central** | Recalage | API (interne) | Calcul de corrélation croisée |

## 5. Avantages
*   **Scalabilité :** Un seul serveur Python peut gérer des centaines de clients Java (les messages JSON sont très légers).
*   **Vie Privée :** Les enregistrements complets de l'utilisateur ne quittent jamais sa machine.
*   **Fiabilité :** Même si le serveur Python tombe, le Java peut continuer d'enregistrer sur une base de temps approximative.
