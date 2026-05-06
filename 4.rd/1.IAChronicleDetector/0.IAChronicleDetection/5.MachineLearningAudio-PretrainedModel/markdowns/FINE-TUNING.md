# Guide de Fine-Tuning du Modèle de Détection de Chroniques

Ce document explique comment fine-tuner le modèle Wav2Vec2 pour la détection binaire de chroniques radio (Chronique vs Background).

## 1. Structure des Données

Le script d'entraînement (`src/train_without_names.py`) s'appuie sur deux sources de données situées en dehors du dépôt (chemins relatifs) :

- **Audios** : Dossiers structurés par radio et date (ex: `AUDIO_ROOT/radio/date/fichier.mp3`).
- **Timecodes** : Fichiers texte contenant les segments identifiés (ex: `TIMECODE_ROOT/radio/news/date_new_from_audio.txt`).

Le format des timecodes attendu est :
`[HH:MM:SS:mmm] - [HH:MM:SS:mmm] Label`

## 2. Processus d'Entraînement

### Préparation et Optimisation Disque
L'entraînement audio consomme énormément de cache. Le script inclut des optimisations critiques pour fonctionner sur des machines avec peu d'espace disque (ex: < 50 GB) :
- **Nettoyage auto** : Supprime le cache de génération Hugging Face au démarrage.
- **Lazy Sampling** : Le sous-échantillonnage se fait *pendant* la génération des données (streaming-like) pour éviter de créer des fichiers temporaires géants.
- **Checkpoints limités** : Seul le meilleur modèle est conservé sur le disque.

### Commande de base
Pour lancer un entraînement avec un équilibre 50/50 entre les chroniques et le bruit de fond :
```bash
python src/train_without_names.py --background_percent 50 --epochs 10
```

### Paramètres principaux
| Paramètre | Description | Défaut |
| :--- | :--- | :--- |
| `--epochs` | Nombre de cycles d'entraînement complets. | 10 |
| `--background_percent` | Pourcentage cible de segments "background" dans le dataset final. | None (tout garder) |
| `--chronicle_step` | Pas de temps (en sec) pour découper les chroniques. | 5.0 |
| `--background_step` | Pas de temps (en sec) pour découper le bruit de fond. | 10.0 |
| `--tags` | Tags pour le suivi sur Weights & Biases (WandB). | "" |

## 3. Stratégie d'Échantillonnage

- **Segments** : Le modèle travaille sur des segments de **10 secondes** (fixé par `MAX_DURATION`).
- **Chevauchement** : En utilisant un pas (`step`) plus petit que la durée (ex: 5s pour des segments de 10s), on crée un chevauchement qui augmente la taille du dataset et la robustesse du modèle.
- **Équilibrage** : Puisqu'il y a généralement beaucoup plus de "background" que de "chroniques" dans une émission, utilisez `--background_percent 50` pour éviter que le modèle ne devienne paresseux et ne prédise que du silence/bruit.

## 4. Sortie du Modèle

Les résultats sont sauvegardés dans `./model_output_binary/` :
- `model.safetensors` : Les poids du modèle fine-tuné.
- `config.json` : La configuration du modèle.
- `label_mapping.json` : La correspondance entre les IDs (0, 1) et les labels (background, chronique).
- `preprocessor_config.json` : Configuration de l'extraction de caractéristiques audio.

## 5. Suivi (WandB)

L'entraînement est automatiquement loggé sur **Weights & Biases**. Vous pouvez y suivre en temps réel :
- La perte (Loss) d'entraînement et de validation.
- L'exactitude (Accuracy) et le score F1.
- La consommation des ressources matérielles.

## 6. Fonctionnement Technique : Pipeline de Données

Le passage des données au modèle suit un pipeline optimisé pour gérer de gros volumes audio sans saturer la RAM :

### A. Chargement "Lazy" (Générateur Python)
Au lieu de charger des milliers d'heures audio en mémoire, le script utilise la fonction `segment_generator`. 
1. Elle lit les fichiers audio un par un avec `pydub`.
2. Elle découpe les segments de 10s à la volée.
3. Elle utilise `yield` pour ne fournir au système que ce dont il a besoin à l'instant T.

### B. Objet `Dataset` de Hugging Face
La méthode `Dataset.from_generator` transforme ce générateur en un objet structuré. Grâce aux optimisations apportées, cet objet est stocké temporairement sur le disque sous forme de fichiers "mappés en mémoire" (Memory-Mapped Files), ce qui permet un accès ultra-rapide sans consommer de RAM.

### C. Extraction de Caractéristiques (Feature Extraction)
Le modèle Wav2Vec2 ne comprend pas directement les fichiers `.mp3`. La `preprocess_function` utilise le `Wav2Vec2FeatureExtractor` pour :
1. Vérifier le taux d'échantillonnage (16kHz).
2. Normaliser l'amplitude du son.
3. Transformer l'onde sonore en une série de vecteurs numériques (Tensors) que le réseau de neurones peut traiter.

### D. La classe `Trainer`
Enfin, le `Trainer` de Hugging Face orchestre tout :
- Il récupère les données traitées.
- Il les regroupe en "batches" (paquets).
- Il les passe au modèle pour le calcul des gradients.
- Il met à jour les poids du modèle pour minimiser l'erreur de détection.
