# IA Chronicle Detector - Machine Learning Audio

Ce projet est un outil de détection automatique de segments audio (chroniques ou publicités) utilisant des techniques d'apprentissage automatique (Machine Learning). Il permet de segmenter des fichiers audio longs, d'extraire des caractéristiques acoustiques et d'entraîner un classifieur pour identifier les zones d'intérêt.

Dans cette nouvelle approche, on entraîne un modèle avec:
 - des fichiers ne contenant pas de chroniques
 - et des fichiers qui contiennent uniquement des chroniques.


## Modèle de Machine Learning

Le modèle utilisé par défaut est un **Random Forest (Forêt Aléatoire)**. 

### Pourquoi Random Forest ?
- **Efficacité** : Il offre un excellent compromis entre vitesse d'entraînement et précision.
- **Robustesse** : Il gère bien les données de grande dimension (nombreuses caractéristiques audio).
- **Flexibilité** : Le projet supporte également d'autres architectures (via `src/main.py`) :
    - **SVM** (Support Vector Machine) : Pour une précision accrue sur de petits jeux de données.
    - **MLP** (Multi-Layer Perceptron) : Un réseau de neurones simple pour capturer des relations complexes.

## Caractéristiques Audio Extraites

Pour chaque segment de 3 secondes, le système extrait une signature acoustique riche :
- **MFCC** (Mel-Frequency Cepstral Coefficients) : Capture le timbre de la voix.
- **Énergie par bande** : Analyse la répartition fréquentielle.
- **Zero-Crossing Rate** : Détecte la présence de percussions ou de bruits.
- **RMS (Root Mean Square)** : Mesure l'intensité sonore.
- **Caractéristiques Spectrales** : Centroid, Rolloff et Bandwidth pour analyser la "brillance" du son.

## Structure du Projet

- `src/main.py` : Script principal pour l'entraînement et la détection.
- `src/timecodes_files/` : Contient les annotations (vérité terrain) au format `MM:SS - MM:SS`.
- `models/` : Stocke les modèles entraînés (`.pkl`).
- `src/publicités/` : Dossier de sortie pour les segments détectés et extraits.
- `training_config.txt` : Fichier de configuration pour l'entraînement multi-fichiers.

## Utilisation

### Installation
Le projet utilise `uv` pour la gestion des dépendances.
```bash
uv sync
```

### Entraînement
Pour lancer un nouvel entraînement à partir des fichiers configurés dans `src/training_config.txt` :
```bash
python train_model.py
```

### Détection
Pour analyser un fichier audio avec un modèle déjà existant :
```bash
python detect_chronicles.py --model models/rlac-audio-segmenter-chroniques_model.pkl chemin/vers/votre_audio.mp3
```

## Comment tester le modèle

1. **Préparer les données** : Assurez-vous que vos fichiers audio et leurs fichiers de timecodes correspondants sont correctement référencés dans `src/training_config.txt`.
2. **Entraîner** : Lancez `python train_model.py`. Cela générera un fichier `.pkl` dans le dossier `models/`.
3. **Exécuter** : Utilisez le script `detect_chronicles.py` sur un nouvel enregistrement pour voir si les chroniques sont correctement identifiées.
4. **Vérifier** : Les segments détectés seront extraits dans le dossier `publicités/` (si l'option n'est pas désactivée) et les timecodes seront affichés dans la console.


## Publication du modèle sur Hugging Face

```bash
# Installation et login
brew install hf
hf auth login

# Upload the model into repo `eglantinefonrose/rlac-audio-segmenter-chroniques`
# Remark: The last `.` is the path within the repo
hf upload eglantinefonrose/rlac-audio-segmenter-chroniques ./models .
```

Le modèle est disponible sur: https://huggingface.co/eglantinefonrose/rlac-audio-segmenter-chroniques


## Améliorations à venir

Le projet est actuellement en phase de R&D. Les pistes d'amélioration incluent :
- L'augmentation des données pour une meilleure généralisation.
- Le réglage fin des seuils de confiance (actuellement fixé à 89% pour limiter les faux positifs).
- L'ajout de nouvelles caractéristiques audio pour distinguer plus finement les chroniques des publicités.

## Conclusion perso

Essai 1 (entrainement sur 9 fichiers) : approche pas concluante (chroniques rassemblées sans raison et coupées en plein milieu).
