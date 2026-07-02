J'ai conçu et implémenté un pipeline de test complet pour votre système GroovyMorning. Ce pipeline couvre les tests unitaires, d'intégration et un
  scénario de bout en bout (End-to-End) automatisé.

  Réalisations clés :

   1. Tests Unitaires Python : Création d'une suite de tests pour live_radio_segmenter.py (simulant la détection de jingles sans charger de modèles
      lourds comme Whisper).
   2. Tests d'Intégration Java : Ajout de tests pour valider la réception des événements Socket.IO et le déclenchement de la logique
      d'enregistrement (DynamicRecordingService).
   3. Pipeline End-to-End (E2E) :
       * Assets de test : Script de génération d'un flux audio (test_flux.wav) mélangeant silence et jingles réels de France Inter.
       * Orchestration Docker : Fichier docker-compose.e2e.yml pilotant Postgres, l'API Python, le Backend Java et le Segmenter.
       * Automate de test : Script e2e/test_runner.py qui injecte l'audio dans les pipes système et vérifie via l'API Java que la chronique a bien
         été enregistrée.
   4. Documentation : Création du fichier TESTING.md détaillant comment lancer chaque étape du pipeline.

  Architecture du Pipeline de Test :

   * Entrée : Un fichier WAV simulant le direct de France Inter.
   * Composant Python : Détecte le jingle, notifie l'API Python qui émet un événement Socket.IO.
   * Composant Java : Intercepte l'événement, démarre FFmpeg pour capturer le flux depuis un pipe, et génère les fichiers HLS (m3u8/fmp4).
   * Validation : Le script de test interroge l'API Java (/api/getUserChronicles) pour confirmer que la chronique est listée et prête à être
     consommée par l'app Android.

  Comment lancer le pipeline :

  Consultez le fichier TESTING.md (./TESTING.md) pour les instructions détaillées. La commande principale pour le test E2E est :

   1 docker-compose -f docker-compose.e2e.yml up --build --abort-on-container-exit

  Note : Pour le composant Android, j'ai validé le contrat d'interface API en inspectant les classes générées (APIService, MainViewModel), assurant
  ainsi la compatibilité entre le Backend Java et l'application mobile.

