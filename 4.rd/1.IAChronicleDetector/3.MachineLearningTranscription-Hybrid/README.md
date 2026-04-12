# Détection Automatique de Chroniques Radio

Ce projet vise à détecter et segmenter automatiquement les chroniques (séquences thématiques) au sein de transcriptions de programmes radio (fichiers SRT). Il utilise des techniques d'apprentissage automatique pour identifier les moments où une chronique commence, se déroule et se termine.

## Analyse de transcriptions

Dans le projet `./1.MachineLearningAudio` on faisait de l'analyse du SON. 
Le modèle travaille sur des caractéristiques acoustiques.
   * Entrées : Fréquences audio, Rythme, Texture sonore (MFCC, Spectral Contrast, etc.).
   * Objectif : Détecter la signature sonore d'une chronique (générique, musique de fond spécifique) sans lire le texte.

 Dans le projet `./2.MachineLearningTranscription` on fait de l'analyse du TEXTE. 
 Ici le modèle (Random Forest aussi) qui se trouve dans la classe RadioChroniqueClassifier (dans train.py) travaille sur des caractéristiques linguistiques.
   * Entrées : Mots utilisés, sens des phrases (Embeddings CamemBERT), ponctuation et métadonnées de transcription.
   * Objectif : Détecter une chronique en "lisant" ce qui est dit (par exemple, identifier des phrases de présentation ou des thématiques spécifiques).


## Modèles d'IA

Le projet propose deux architectures de modèles :

1.  **Modèle Hybride (Recommandé) :** Une architecture moderne combinant :
    *   **CamemBERT** : Pour l'extraction de représentations sémantiques riches du texte.
    *   **Bi-LSTM** : Pour la modélisation de la séquence temporelle des segments.
    *   **CRF (Conditional Random Fields)** : Pour garantir une cohérence dans la segmentation (ex: un segment "milieu de chronique" doit suivre un "début de chronique").
    *   **Focal Loss** : Pour gérer le déséquilibre des classes (les débuts de chroniques sont rares).

2.  **Modèle Random Forest (Classique) :** Un modèle robuste utilisant :
    *   Des features textuelles (TF-IDF) et acoustiques/temporelles.
    *   Une fenêtre glissante pour capturer le contexte local.
    *   Plus léger et rapide à entraîner sur CPU.

## Fonctionnalités

*   **Extraction de features hybrides** : Word/char count, ponctuation, détection de jingles, heure de la journée, embeddings CamemBERT.
*   **Support SRT personnalisé** : Gestion des index avec marqueurs temporels `[HH:MM:SS]`.
*   **Post-traitement intelligent** : Lissage des probabilités, fusion des segments proches et filtrage par durée minimale.
*   **Évaluation détaillée** : Calcul de la précision, du rappel, du score F1 et de l'IoU (Intersection over Union).

## Installation

Le projet utilise `uv` pour la gestion des dépendances.

```bash
# Installer les dépendances
uv sync
```

## Utilisation

### 1. Entraînement

L'entraînement se configure via `training_config.txt`. Chaque ligne doit suivre le format : `chemin_srt|chemin_timecodes|nom_emission`.

```bash
# Lancer l'entraînement (par défaut le modèle hybride)
uv run train.py
```

Les modèles seront sauvegardés dans le dossier `models/`.

### 2. Prédiction

Pour prédire les chroniques sur un nouveau fichier SRT :

```bash
uv run predict.py
```

Vous pouvez modifier le script `predict.py` pour pointer vers votre fichier SRT et votre modèle.

## Structure du Projet

*   `train.py` : Définition des architectures (Random Forest, LSTM, Hybrid) et pipeline d'entraînement.
*   `predict.py` : Pipeline d'inférence, post-traitement et évaluation.
*   `utils.py` : Utilitaires de chargement SRT, parsing de timecodes et extraction de features.
*   `models/` : Contient les modèles entraînés (`.pkl` pour Random Forest/Base, `.pt` pour PyTorch Hybrid).

## Évaluation

Le script de prédiction inclut une évaluation automatique si un fichier de "vérité terrain" (ground truth) est fourni. Il compare les intervalles prédits avec les intervalles réels en utilisant :
*   **Tolérance aux bordures** : Match si le début et la fin sont proches à X secondes près.
*   **IoU (Intersection over Union)** : Mesure le recouvrement global des segments.
