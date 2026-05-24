# 2. Transcription Generation

Ce dossier contient les scripts d'automatisation de la transcription audio utilisant différents modèles.

## Aperçu des Scripts

Deux scripts sont disponibles, partageant la même logique de parcours de fichiers mais utilisant des moteurs différents :

1.  **`prt-generate-transcripts-with-whisper.py`** : Utilise `whisper.cpp` (C++) via son interface CLI.
2.  **`prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py`** : Utilise le modèle `kyutai/stt-1b-en_fr` via la bibliothèque Python `transformers`.

### Aide et Paramètres
Les deux scripts supportent l'argument `--help` pour afficher la liste complète des options disponibles :

```bash
./prt-generate-transcripts-with-whisper.py --help
./prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py --help
```

---

## 1. Script : Whisper.cpp (Whisper)

Ce script est un wrapper pour `whisper-cli`.

### Caractéristiques
- **Optimisation** : Utilise `whisper.cpp` pour des performances CPU/GPU optimales.
- **Fiabilité** : Force la langue en français (`-l fr`).
- **Dépendances** : Nécessite `whisper-cli` installé et un modèle au format `.bin` (GGML).

### Exemple d'utilisation
```bash
./prt-generate-transcripts-with-whisper.py --model-path /chemin/vers/modèle.bin
```

---

## 2. Script : Kyutai STT (Moshi/STT-1B)

Ce script utilise le modèle de Kyutai pour une transcription bilingue (FR/EN) à très faible latence.

### Caractéristiques
- **Natif Python** : Utilise `transformers`, `torch` et `librosa`.
- **SRT Intelligent** : Reconstruit les fichiers `.srt` à partir des jetons de timestamps du modèle.
- **Qualité** : Modèle optimisé pour le français avec gestion native du débit à 24kHz.
- **Découverte dynamique** : Scanne automatiquement tous les dossiers dans `audio/`.

### Exemple d'utilisation
```bash
./prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py --device mps
```

---

## Fonctionnalités Communes

Les deux scripts partagent les fonctionnalités suivantes :
- **Parcours Récursif** : Traite tous les fichiers audio (`.mp3`, `.wav`, `.m4a`, etc.) dans les sous-dossiers.
- **Gestion d'état** : Une fois transcrit, le fichier audio est déplacé vers un dossier `audio-done` (sauf si `--no-move-to-done-when-processed` est utilisé).
- **Structure de sortie** : Recrée la hiérarchie exacte des dossiers (par station et par date) dans le répertoire des transcriptions.

## Installation des Dépendances

Ce projet utilise [uv](https://github.com/astral-sh/uv) pour la gestion de l'environnement et des dépendances.

Pour configurer l'environnement et installer les dépendances :

```bash
# Créer l'environnement et installer les dépendances
uv sync

# Lancer les scripts via uv run
uv run ./prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py
```
