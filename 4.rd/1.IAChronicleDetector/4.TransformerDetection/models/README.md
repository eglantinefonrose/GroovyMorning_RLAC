# Documentation des Modèles de Détection de Chroniques

Ce dossier contient les modèles entraînés pour identifier les segments de chroniques dans les transcriptions radio.

## Modèle Transformer (DistilCamemBERT)

C'est le modèle principal généré par `train.py`. Nous avons opté pour une version distillée afin d'accélérer les cycles d'expérimentation tout en conservant d'excellentes performances.

- **Type de modèle** : Transformer (Architecture BERT), utilisant `cmarkea/distilcamembert-base`.
- **Nombre de paramètres** : **~68 millions** (au lieu de 110M pour la version base).
- **Méthode d'apprentissage** : **Fine-tuning** sur des segments de transcriptions.
- **Optimisations** :
    - **Modèle Distillé** : Utilise une version compressée de CamemBERT qui conserve environ 95% des performances tout en étant beaucoup plus légère.
    - **Fenêtre Contextuelle** : `max_length` de 128 tokens pour un équilibre optimal entre contexte et temps de calcul.
    - **Efficacité** : Le modèle est suffisamment léger pour être ultra-rapide en Python standard, sans nécessiter de formats de quantification complexes comme GGUF.

### Pourquoi DistilCamemBERT ?
C'est le compromis idéal : il comprend parfaitement les nuances du français mais s'entraîne et s'exécute beaucoup plus vite que le modèle standard.

## Utilisation

Le script `train.py` entraîne ce modèle. Pour utiliser ce modèle en prédiction, le script `predict.py` doit pointer vers le dossier `models/camembert_chronicle`.

## Fichiers de sortie
- `camembert_chronicle/` : Dossier contenant les poids du modèle, la configuration et le tokenizer au format Hugging Face.

## Méthode d'entraînement
L'entraînement est effectué sur l'intégralité des données disponibles (transcriptions Whisper couplées à des timecodes de référence) pour maximiser la capacité de détection sémantique des segments de chroniques.
