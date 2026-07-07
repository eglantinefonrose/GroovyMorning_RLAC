# Audio Chronicle Detector - Wav2Vec2 Fine-Tuning

Ce projet permet de fine-tuner un modèle `wav2vec2-large-xlsr-53-french` pour la classification de segments audio (détection de chroniques radio) et d'effectuer des prédictions sur de nouveaux fichiers audio.

## Installation

1. Assurez-vous d'avoir Python 3.8+ et `ffmpeg` installés sur votre système.
2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

## Structure du Projet

- `train.py` : Script d'entraînement / fine-tuning.
- `predict.py` : Script de prédiction utilisant le modèle entraîné.
- `requirements.txt` : Liste des dépendances Python.
- `model_output/` : Répertoire où le modèle et les mappings de labels sont sauvegardés.

## Entraînement (`train.py`)

Le script `train.py` effectue les étapes suivantes :
1. **Découverte du dataset** : Il parcourt les dossiers `@assets/0.media/audio` et `@assets/2.humanOutputs/.../timecode_chroniques` pour appairer les fichiers audio avec leurs fichiers de timecodes correspondants.
2. **Priorité des fichiers** : Si un fichier `_trimmed` est présent dans le dossier d'émission, il est utilisé en priorité.
3. **Extraction des segments** : Les fichiers audio sont découpés en segments selon les timecodes fournis.
4. **Prétraitement** : Les segments sont échantillonnés à 16 000 Hz et normalisés.
5. **Fine-tuning** : Utilise `Wav2Vec2ForSequenceClassification` avec une tête de classification adaptée au nombre de chroniques uniques trouvées.
6. **Logging** : Intégration avec **Weights & Biases (WandB)** pour le suivi des métriques (loss, accuracy).

### Lancement de l'entraînement
```bash
python train.py --epochs 10
```

**Arguments optionnels :**
- `--epochs` : Nombre d'époques d'entraînement (défaut: 10).
- `--cleanup_cache` : Vide le cache Hugging Face avant de commencer. Utile en cas d'erreur de disque ou de données corrompues, mais ralentit le démarrage (re-génération des segments).
- `--background_percent` : Pourcentage cible de segments "background" dans le dataset (ex: 70).

### Lancement en mode offline
HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python train.py

### Astuces pour la vitesse
- **Multiprocessing** : Vous pouvez accélérer la génération du dataset en ajoutant `num_proc=4` (ou le nombre de cœurs de votre Mac) dans l'appel `dataset.map` à l'intérieur des scripts.
- **Cache** : N'utilisez `--cleanup_cache` que si vous changez radicalement de données ou si vous avez des erreurs de lecture.

## Prédiction (`predict.py`)

Le script `predict.py` permet d'analyser un fichier audio (`.mp3` ou `.m4a`) pour détecter les chroniques qu'il contient.

### Fonctionnement
- Utilise une **fenêtre glissante** (par défaut 10s avec 5s d'overlap).
- Prédit le label pour chaque fenêtre.
- Fusionne les fenêtres consécutives ayant le même label pour produire des segments cohérents.

### Utilisation
```bash
python predict.py chemin/vers/audio.mp3 --output resultat.json
```

**Arguments :**
- `audio` : Chemin vers le fichier audio.
- `--window` : Taille de la fenêtre en secondes (défaut: 10.0).
- `--overlap` : Overlap entre les fenêtres en secondes (défaut: 5.0).
- `--output` : (Optionnel) Chemin pour exporter les résultats en JSON.

## Intégration WandB

L'intégration WandB est activée par défaut dans `train.py`. Elle permet de visualiser l'évolution de la précision et de la perte durant l'entraînement. 
Pour l'utiliser, assurez-vous d'être connecté à votre compte WandB (`wandb login`). Le projet est nommé `IAChronicleDetector`.

## Hypothèses sur le format des timecodes

Le format détecté et utilisé pour le parsing est le suivant :
`[HH:MM:SS:mmm] - [HH:MM:SS:mmm] Nom_de_la_chronique.mp3`
Le script extrait les deux timecodes (début et fin) et utilise le reste de la ligne comme label (en retirant les extensions `.mp3` ou `.m4a`).

python evaluate_quality.py --audio "../../../@assets/3.modelEvaluationData/france-inter/audio/27-05-2026.m4a" --model ast --acceleration 5.0