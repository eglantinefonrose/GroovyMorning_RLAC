# IA Chronicle Detector - Data Creation

Ce projet contient une suite d'outils pour la création d'un dataset destiné à la détection automatique de chroniques radio dans des flux audio complets.

Le pipeline se compose de trois étapes principales :
1. **Collecte de données** : Téléchargement des émissions intégrales et des chroniques individuelles.
2. **Transcription** : Génération de transcriptions textuelles (SRT) via Whisper.
3. **Alignement** : Détermination des timecodes exacts des chroniques au sein des émissions intégrales.

## Structure du projet

- **`0.DownloadChroniquesAndFullRadioProgramAutomaticly/`** : Scripts de téléchargement pour différentes stations (France Inter, France Info, France Culture, RTL).
- **`1.ChronicleTimecodeGenerationFromAudios/`** : Outils d'alignement pour retrouver les chroniques dans les intégrales à partir des transcriptions.
- **`2.TranscriptionGeneration/`** : Automatisation de la transcription audio en utilisant `whisper.cpp`.

## Flux de travail (Workflow)

1. Utiliser les scripts du dossier `0` pour récupérer les fichiers audio (intégrales + chroniques).
2. Utiliser le script du dossier `2` pour transcrire tous ces fichiers audio en format SRT.
3. Utiliser le script du dossier `1` pour générer les fichiers de timecodes en comparant les transcriptions des chroniques avec celles des intégrales.

Les fichiers média et les sorties des modèles sont généralement stockés dans un dossier `@assets` (non inclus dans ce dépôt).
