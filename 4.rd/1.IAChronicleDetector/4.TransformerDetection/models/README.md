# Documentation des Modèles de Détection de Chroniques

Ce dossier contient les modèles entraînés pour identifier les segments de chroniques dans les transcriptions radio.

## 1. Modèle Transformer (DistilCamemBERT) - *Version Optimisée*

C'est le modèle principal actuellement généré par `train.py`. Nous avons opté pour une version "nerveuse" afin d'accélérer les cycles d'expérimentation.

- **Type de modèle** : Transformer (Architecture BERT), utilisant `cmarkea/distilcamembert-base`.
- **Nombre de paramètres** : **~68 millions** (au lieu de 110M pour la version base).
- **Méthode d'apprentissage** : **Fine-tuning**.
- **Optimisations "Fast-Training"** :
    - **Modèle Distillé** : Utilise une version compressée de CamemBERT qui conserve environ 95% des performances tout en étant beaucoup plus légère.
    - **Fenêtre Contextuelle Réduite** : `max_length` passé de 256 à 128 tokens, ce qui divise par deux le temps de calcul par segment.
    - **Batch Size augmenté** : Passage à 16 pour mieux exploiter les capacités de calcul parallèle.

### Comparaison avec MLX et GGUF
- **MLX** : Framework Apple Silicon. Bien que compatible, notre modèle est déjà suffisamment léger pour être ultra-rapide en Python standard.
- **GGUF** : Format de quantification. Non nécessaire ici car le modèle fait moins de 300 Mo, contre plusieurs Go pour les LLMs nécessitant du GGUF.
- **Pourquoi DistilCamemBERT ?** C'est le compromis idéal : il comprend parfaitement le français mais s'entraîne et s'exécute **2x plus vite** que le modèle standard.

---

## 2. Modèle Random Forest (Legacy)

Modèle historique basé sur des caractéristiques extraites manuellement.

- **Architecture** : Forêt d'arbres décisionnels (Scikit-learn).
- **Entrées** : Vecteurs TF-IDF + caractéristiques structurelles (durée, position, présence de jingles).
- **Fichier** : `pro_chronicle_model.joblib`.

## Utilisation

Le script `train.py` entraîne désormais la version **Distillée**. Pour utiliser ce modèle en prédiction, assurez-vous que `predict.py` pointe vers le dossier `models/camembert_chronicle`.

## Fichiers de sortie
- `camembert_chronicle/` : Poids du modèle, configuration et tokenizer.
- `rf_metrics.json` : Métriques de performance du modèle Random Forest.

## Utilisation avec entrainement sur les données qui repertorient toutes les chroniques / annonces : détection de une chronique qui va du début à la fin
