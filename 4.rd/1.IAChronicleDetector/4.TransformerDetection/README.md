# Transformer Chronicle Detector

Ce projet utilise un modèle CamemBERT (BERT pour le français) pour détecter les chroniques dans les transcriptions d'émissions de radio.

## Installation

Assurez-vous d'avoir `uv` installé, ou utilisez `pip` :

```bash
pip install -r requirements.txt
# Ou via uv
uv sync
```

## Synchronisation des Assets (Hugging Face)

Les données d'entraînement (SRT et Timecodes) ne sont pas stockées sur GitHub. Elles sont synchronisées via Hugging Face Datasets.

### Pousser les données (Upload)
Pour envoyer vos données locales vers Hugging Face :
```bash
uv run hf_push_assets.py eglantinefonrose/rlac-audiotranscript-segmenter-training-dataset
```

### Récupérer les données (Download)
Pour configurer une nouvelle machine (distante ou locale) :
```bash
uv run hf_pull_assets.py eglantinefonrose/rlac-audiotranscript-segmenter-training-dataset
```

## Entraînement

Il est recommandé d'utiliser `uv` pour garantir la reproductibilité, particulièrement sur machine distante :

```bash
# Installation des dépendances
uv sync

# Lancement de l'entraînement (Valeurs par défaut)
uv run train.py

# Personnalisation de l'entraînement
uv run train.py --epochs 10 --model "almanach/camembert-base" --tags "nvidia,final-run"
```

### Paramètres disponibles :
- `--epochs` : Nombre de passages complets sur le dataset (par défaut : 4).
- `--model` : Modèle HuggingFace à utiliser (par défaut : `cmarkea/distilcamembert-base`).
- `--tags` : Liste de tags séparés par des virgules pour l'organisation dans WandB.
- `--max_steps` : Nombre maximum de pas d'entraînement (écrase `--epochs` si > 0).
- `--srt_dir` : Répertoire contenant les fichiers `.srt` (par défaut : le dossier `@assets` local).
- `--tc_dir` : Répertoire contenant les fichiers `.txt` de timecodes (par défaut : le dossier `@assets` local).


*Note : L'entraînement sur machine distante (PC NVIDIA) est privilégié pour bénéficier de l'accélération CUDA.*

## Monitoring & Logs (WandB)

Le projet utilise **Weights & Biases (WandB)** pour le suivi des métriques en temps réel.

1. **Installation** : `uv add wandb`
2. **Connexion** : `uv run wandb login`
3. **Tableau de bord** : Les courbes de Loss et de F1-score sont consultables sur votre interface WandB sous le projet **`RLAC`**.

Le modèle sera sauvegardé dans le dossier `models/camembert_chronicle`.

## Détection (Prédiction)

Pour lancer la détection sur une nouvelle transcription au format `.srt` :

```bash
python predict.py <chemin_vers_fichier.srt>
```

## Structure du projet

- `train.py` : Script d'entraînement.
- `predict.py` : Script de détection.
- `evaluate_model_precision.py` : Script d'évaluation de la précision (40% Cardinalité / 60% Alignement).
- `hf_push_assets.py` / `hf_pull_assets.py` : Scripts de synchronisation des données via Hugging Face.
- `src/dataset.py` : Gestionnaire de données PyTorch avec fenêtre contextuelle.
- `src/utils.py` : Utilitaires pour le parsing des fichiers SRT et des timecodes.
- `src/evaluation.py` : Logique de scoring RLAC.
- `models/` : Dossier où le modèle entraîné est stocké.

## Résultats
Les frontières entre les chroniques sont parfaitement détectées, mais des fois une chronique en contient deux.
