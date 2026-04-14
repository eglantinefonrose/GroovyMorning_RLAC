# IA Chronicle Detector - Hybrid Transcription Method

Ce projet propose une méthode avancée de détection de chroniques radio basée sur une architecture **Deep Learning Hybride** analysant les transcriptions textuelles (SRT).

Cette approche est conçue pour capturer à la fois le sens profond des paroles et la structure séquentielle d'une émission radio.

## Approche Technique

Le modèle repose sur une architecture à trois étages :
1.  **Compréhension Sémantique (CamemBERT)** : Chaque segment de texte est transformé en vecteurs de caractéristiques riches (embeddings) par le modèle de langage CamemBERT, permettant de comprendre le contexte et le sujet abordé.
2.  **Modélisation Séquentielle (Bi-LSTM)** : Un réseau de neurones récurrent bidirectionnel analyse la suite des segments pour comprendre la progression de l'émission et identifier les transitions.
3.  **Cohérence Temporelle (CRF)** : Une couche *Conditional Random Field* garantit que la séquence de labels prédite est logiquement possible (par exemple, gérer proprement le début, le milieu et la fin d'une chronique).

L'entraînement utilise une **Focal Loss** pour surmonter le déséquilibre des classes (les débuts de chroniques étant des événements rares).

## Structure du Projet

*   `train.py` : Script pour entraîner l'extracteur de caractéristiques et le classifieur séquentiel.
*   `predict.py` : Script de détection utilisant le duo de modèles pour une précision maximale.
*   `utils.py` : Utilitaires de traitement SRT et labellisation séquentielle.
*   `models/` : Contient les deux fichiers indissociables :
    *   `*_base.pkl` : L'extracteur de features et embeddings.
    *   `*_hybrid.pt` : Le modèle PyTorch (LSTM+CRF).

## Installation

Cette méthode nécessite des bibliothèques de Deep Learning.

```bash
# Avec uv (recommandé)
uv sync

# Le projet utilise automatiquement le GPU (CUDA) ou l'accélération Apple Silicon (MPS) si disponibles.
```

## Utilisation

### Entraînement
Configurez vos fichiers dans `training_config.txt`, puis :
```bash
python train.py
```

### Prédiction
Pour lancer la détection sur un fichier SRT :
```bash
python predict.py
```

## Modèle
Une documentation détaillée de l'architecture est disponible dans : [models/README.md](models/README.md)

## Publication du modèle sur Hugging Face

```bash
# Installation et login
brew install hf
hf auth login

# Upload the model into repo `eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest`
# Remark: The last `.` is the path within the repo
hf upload eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid ./models .
```

Le modèle est disponible sur: https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid
