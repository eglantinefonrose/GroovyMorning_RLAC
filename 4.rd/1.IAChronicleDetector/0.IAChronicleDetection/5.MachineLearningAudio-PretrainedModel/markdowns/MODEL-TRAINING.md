# Guide d'Entraînement des Modèles

Ce document explique le fonctionnement de l'entraînement pour les détecteurs audio de chroniques, les différences entre les variantes, et comment utiliser les options d'échantillonnage pour équilibrer le jeu de données.

## Architecture Globale

Les modèles sont basés sur l'architecture **Wav2Vec2** (`facebook/wav2vec2-large-xlsr-53-french`), affinée (fine-tuned) pour la classification de séquences audio.

1.  **Extraction de caractéristiques** : Le modèle prend des segments audio de 10 secondes.
2.  **Génération de segments** : Les scripts découpent les fichiers audio longs en segments plus courts en utilisant les timecodes fournis par les experts humains.
3.  **Classification** : Le modèle prédit si un segment est une chronique ou du bruit de fond (background).

---

## Variantes d'Entraînement

### 1. Entraînement Multi-classes (`src/train.py`)
Ce script entraîne le modèle à reconnaître **chaque type de chronique spécifiquement** (ex: "journal-7h", "laurent-gerra", "oeil-philippe", etc.) en plus de la classe "background".

*   **Usage** : Idéal si vous voulez savoir *quelle* chronique est diffusée.
*   **Sortie** : `model_output/`

### 2. Entraînement Binaire (`src/train_without_names.py`)
Ce script regroupe toutes les chroniques sous une seule étiquette unique : **"chronique"**. Il ne reste donc que deux classes : "chronique" et "background".

*   **Usage** : Idéal pour une détection robuste de la présence d'une chronique, sans se soucier de son nom. C'est souvent plus précis car les données sont plus denses pour une seule classe.
*   **Sortie** : `model_output_binary/`

---

## Équilibrage du Jeu de Données

L'un des plus grands défis est le déséquilibre : il y a beaucoup plus de "background" que de "chroniques" dans une radio. Nous avons deux leviers pour contrôler cela.

### Leviers de "Pas" (Sampling Steps)
Ces options contrôlent la fréquence de découpe lors de la lecture des fichiers.

*   `--chronicle_step` (Défaut: 5s) : Un segment de 10s est extrait toutes les 5s dans une zone de chronique.
*   `--background_step` : Un segment de 10s est extrait toutes les X secondes dans les zones de background.
    *   Plus la valeur est **basse**, plus vous aurez de segments de cette classe.
    *   *Exemple* : `--background_step 5.0` doublera la quantité de background par rapport à `--background_step 10.0`.

### Levier de Pourcentage (`--background_percent`)
C'est la méthode la plus précise. Le script génère les données, puis effectue un **sous-échantillonnage (downsampling)** automatique pour atteindre le ratio exact demandé.

*   **Principe** : Si vous demandez 80%, le script calculera combien de segments de chaque classe garder pour que le background représente exactement 80% du total.
*   **Avantage** : Vous contrôlez la proportion exacte vue par le modèle, ce qui évite les biais vers une classe.

---

## Performance et Gestion du Cache

L'entraînement de modèles audio est gourmand en ressources. Voici quelques options pour gérer la performance et l'espace disque.

### Gestion du Cache (`--cleanup_cache`)
Hugging Face génère des fichiers temporaires (cache) lors de la création du jeu de données. Ces fichiers peuvent parfois devenir très volumineux ou se corrompre.

*   **Usage** : `python src/train_without_names.py --cleanup_cache`
*   **Quand l'utiliser** : Si vous rencontrez des erreurs de type `ArrowInvalid` ou si votre disque est saturé.
*   **Impact** : Si activé, le script recalculera tous les segments audio (découpe et ré-échantillonnage), ce qui ajoute environ **5 à 10 minutes** de préparation avant l'entraînement. Sans cette option, le script réutilise les segments déjà calculés s'ils sont disponibles.

### Accélération Matérielle
Les scripts détectent automatiquement le meilleur matériel disponible :
*   **NVIDIA GPU** : Via CUDA.
*   **Mac Apple Silicon** : Via MPS (Metal Performance Shaders).
*   **CPU** : Par défaut si aucun GPU n'est trouvé.

---

## Exemples de Commandes

### Entraînement standard (Équilibre naturel)
```bash
python src/train_without_names.py --epochs 10
```

### Entraînement avec 70% de Background (Recommandé)
Pour que le modèle ne soit pas trop sensible et n'invente pas des chroniques partout.
```bash
python src/train_without_names.py --background_percent 70
```

### Entraînement avec très peu de données chroniques
Si vous voulez tester la robustesse avec moins d'échantillons de chroniques :
```bash
python src/train_without_names.py --chronicle_step 15.0 --background_percent 90
```

---

## Suivi des Expériences (WandB)

Tous les entraînements sont loggués sur **Weights & Biases**. Vous pouvez y retrouver :
*   La courbe de perte (loss) et de précision (accuracy).
*   Le score **F1** (très important pour les classes déséquilibrées).
*   La configuration utilisée (`background_percent`, `chronicle_step`, etc.).

Pour ajouter un tag à votre run :
```bash
python src/train_without_names.py --tags "test-equilibre,v2"
```
