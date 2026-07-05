  ### 🚀 Démarrage Rapide (Docker Compose)

  Le moyen le plus simple de lancer tout le projet (Java + Python + Tunnel) est d'utiliser Docker Compose.

  1.  **Copiez le fichier d'exemple pour l'environnement :**
      ```bash
      cp .env.example .env
      ```
  2.  **Éditez le fichier `.env`** pour y ajouter votre `DEEPSEEK_API_KEY` et éventuellement votre `TUNNEL_TOKEN`.
  3.  **Lancez les services :**
      ```bash
      docker compose up --build
      ```

  Cela démarrera :
  - Le backend Java sur le port **8000**
  - Le segmenter Python sur le port **8001**
  - Le tunnel Cloudflare (si configuré)

  ---

  ### 🛠 Démarrage Manuel (Sans Docker)

  Si vous préférez lancer les serveurs manuellement :

  #### 1. Démarrer le Serveur Principal (Java - Port 8000)

  Ce serveur gère les chroniques, les dossiers du jour et l'API principale utilisée par l'application.

   1 cd 1.RLAC-AudioRecorder
   2 ./gradlew run

  2. Démarrer le Serveur de Segmentation (Python - Port 8001)
  Ce serveur gère les événements en temps réel via WebSockets (début/fin de chronique).

    1 # Allez dans le dossier du segmenter
    2 cd 2.RLAC-IAChronicleSegmenter
    3
    4 # Créez et activez un environnement virtuel (optionnel mais recommandé)
    5 python3 -m venv .venv
    6 source .venv/bin/activate
    7
    8 # Installez les dépendances
    9 pip install -r requirements.txt
   10
   11 # Lancez le serveur API Python
   12 python3 api-server.py

  3. Vérification
  Une fois les serveurs lancés, vous pouvez vérifier qu'ils fonctionnent :
   - Java API : Ouvrez http://localhost:8000/api/status (ou tout autre endpoint comme findTodayFolder) dans votre navigateur.
   - Python API : Ouvrez http://localhost:8001/api/status.

  Conseils :
   - Assurez-vous que votre téléphone est sur le même réseau Wi-Fi que votre ordinateur.
   - Notez l'adresse IP de votre ordinateur (ex: 192.168.1.15) et renseignez-la dans les réglages de l'application Android pour qu'elle puisse
     communiquer avec ces serveurs.