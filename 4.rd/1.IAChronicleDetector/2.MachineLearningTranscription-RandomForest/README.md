# IA Chronicle Detector - RandomForest Transcription Method

Ce projet propose une méthode de détection de chroniques radio basée sur l'analyse textuelle des transcriptions (SRT) en utilisant un algorithme **Random Forest**.

Il s'agit d'une approche légère, rapide et efficace qui ne nécessite pas de GPU.

## Approche Technique

Le modèle analyse le flux de transcription segment par segment en utilisant :
1.  **Extraction de caractéristiques (Features)** :
    *   Durée des segments et métadonnées temporelles.
    *   Statistiques textuelles (nombre de mots, ponctuation).
    *   **TF-IDF** : Analyse de l'importance des mots pour identifier le vocabulaire spécifique aux chroniques.
2.  **Fenêtre Glissante (Contextual Window)** : Pour chaque segment, le modèle prend en compte les caractéristiques des segments adjacents (contexte local) pour améliorer la précision de la détection.
3.  **Classification** : Un classifieur Random Forest robuste qui sépare les chroniques du reste de l'émission.

## Structure du Projet

*   `train.py` : Script pour entraîner le modèle Random Forest à partir de fichiers SRT et de leurs timecodes de référence.
*   `predict.py` : Script pour détecter les chroniques sur une nouvelle transcription.
*   `utils.py` : Fonctions utilitaires pour le parsing SRT et le calcul des caractéristiques.
*   `models/` : Dossier contenant le modèle entraîné (`.pkl`) et sa documentation.

## Installation

Ce projet est conçu pour être très léger.

```bash
# Avec uv (recommandé)
uv sync

# Ou avec pip
pip install -r requirements.txt
```

*Note : Contrairement à la méthode hybride, ce projet ne nécessite pas PyTorch ni de modèles de langage lourds.*

## Utilisation

### Entraînement
Modifiez `training_config.txt` pour pointer vers vos données, puis lancez :
```bash
python train.py
```

### Prédiction
Pour lancer une détection sur un fichier SRT :
```bash
python predict.py
```

## Modèle
Le modèle est sauvegardé sous forme de fichier `.pkl` dans le dossier `models/`.
Documentation détaillée du modèle : [models/README.md](models/README.md)

## Publication du modèle sur Hugging Face

```bash
# Installation et login
brew install hf
hf auth login

# Upload the model into repo `eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest`
# Remark: The last `.` is the path within the repo
hf upload eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest ./models .
```

Le modèle est disponible sur: https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest
