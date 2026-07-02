# Pipeline de Test End-to-End (E2E) - GroovyMorning

Ce pipeline valide le workflow complet :
1. Détection audio par le segmenter Python.
2. Notification via l'API Python (Socket.IO).
3. Enregistrement par le backend Java.
4. Disponibilité via l'API REST pour l'application Android.

## Structure du Pipeline

- `2.RLAC-IAChronicleSegmenter/tests/`: Tests unitaires Python (logique de détection).
- `1.RLAC-AudioRecorder/src/test/java/`: Tests unitaires et d'intégration Java (Socket.IO, recording).
- `e2e/`: Scripts et assets pour le test de bout en bout.
  - `assets/test_flux.wav`: Flux audio de test (10s silence + jingle 7h).
  - `test_runner.py`: Orchestrateur du test E2E.

## Pré-requis

- Docker et Docker Compose.
- FFmpeg (pour générer les assets de test).

## Lancer le Pipeline Complet

### 1. Tests Unitaires Python
```bash
cd 2.RLAC-IAChronicleSegmenter
. .venv/bin/activate
python tests/test_segmenter.py
```

### 2. Tests Unitaires Java
```bash
cd 1.RLAC-AudioRecorder
./gradlew test
```

### 3. Test End-to-End (Docker)
```bash
docker-compose -f docker-compose.e2e.yml up --build --abort-on-container-exit
```

Ce test va :
1. Démarrer Postgres, l'API Python, le Backend Java et le Segmenter.
2. Injecter un flux audio de test dans les pipes.
3. Attendre la détection automatique du jingle "journal de 7h".
4. Vérifier que le Backend Java a bien enregistré la chronique pour l'utilisateur local.

## Scénarios Couverts

- [x] Détection correcte d'une chronique via jingle.
- [x] Transmission Python -> Java via Socket.IO.
- [x] Enregistrement HLS (fmp4) par Java.
- [x] Exposition de la chronique via l'API `/api/getUserChronicles`.
- [x] Isolation par utilisateur (localUserId).

## Scénarios non couverts (en cours)
- Test UI Android automatisé (requiert un émulateur).
- Détection par mots-clés (Whisper) en environnement E2E (trop lent pour CI).
