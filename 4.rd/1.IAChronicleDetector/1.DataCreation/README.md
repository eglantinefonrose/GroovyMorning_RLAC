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
- **`3.AudioMediaTrimming/`** : Outils de découpe (trimming) pour optimiser les fichiers audio.
- **`4.WorkflowAudio/`** : Scripts d'automatisation globale pour le traitement audio (gestion des dates et détection de doublons).

## Flux de travail (Workflows)

### 1. Workflow de Transcription (Génération de Timecodes)
Ce workflow permet de créer un dataset de correspondance entre les fichiers audio intégraux et les chroniques individuelles.

1. **Collecte de données** : Utiliser le script d'automatisation globale :
   - **`4.WorkflowAudio/run_download_workflow.py`** : Télécharge les émissions et chroniques pour toutes les radios (France Inter, Info, Culture, RTL) sur une plage de dates (ex: `python 4.WorkflowAudio/run_download_workflow.py 01-05-2024 31-05-2024`).
   - Ou utiliser les scripts individuels du dossier **`0`**.
2. **Transcription** : Utiliser le script du dossier **`2`** pour transcrire tous ces fichiers audio au format SRT via Whisper.
3. **Alignement** : Utiliser le script du dossier **`1`** pour générer les fichiers de timecodes (`.txt`) en comparant les transcriptions des chroniques avec celles des intégrales.

### 2. Workflow Audio (Trimming et Optimisation)
Ce workflow intervient après la génération des timecodes pour réduire la taille des fichiers audio intégraux en supprimant les parties inutiles (musiques, publicités, autres émissions).

Il existe deux manières de l'utiliser :

#### A. Orchestration automatique (Recommandé)
- **`4.WorkflowAudio/run_full_workflow.py`** : Ce script maître enchaîne le téléchargement global ET le trimming pour toutes les radios sur une période donnée.
  - **Usage** : `python 4.WorkflowAudio/run_full_workflow.py 01-05-2024 31-05-2024`
  - Il gère automatiquement les formats de date et vérifie les doublons pour ne pas retravailler les fichiers déjà optimisés.

#### B. Scripts granulaires
1. **Téléchargement global** : `4.WorkflowAudio/run_download_workflow.py` (Téléchargement seul pour toutes les radios).
2. **Trimming seul** : `4.WorkflowAudio/run_audio_workflow.py` (Optimisation seule pour les fichiers déjà présents).

Le script de trimming génère un nouveau fichier audio `_trimmed` et un fichier de timecodes mis à jour dans un sous-dossier `news/`.

Les fichiers média et les sorties des modèles sont généralement stockés dans un dossier `@assets` (non inclus dans ce dépôt).
