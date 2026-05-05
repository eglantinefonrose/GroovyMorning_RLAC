# Rôle des fichiers de configuration du modèle

Ce document explique le rôle des fichiers de configuration situés dans le répertoire `model_output/`. Ces fichiers sont essentiels pour le chargement correct du modèle et l'interprétation de ses prédictions.

## 1. `model_output/config.json`

Le fichier `config.json` est le fichier de configuration principal du modèle, au format attendu par la bibliothèque Hugging Face Transformers.

### Rôles principaux :
- **Architecture du modèle** : Il définit le type de modèle (par exemple, `Wav2Vec2ForSequenceClassification`) et sa structure (nombre de couches, têtes d'attention, taille cachée, etc.).
- **Hyperparamètres** : Il contient les paramètres utilisés lors de l'entraînement et nécessaires pour l'inférence (dropout, fonctions d'activation, etc.).
- **Mapping des étiquettes (Labels)** : Il inclut les dictionnaires `id2label` et `label2id` qui permettent de convertir les indices numériques prédits par le modèle en noms de chroniques lisibles.
- **Paramètres de prétraitement** : Certains paramètres liés à l'extraction de caractéristiques audio y sont également référencés.

Ce fichier est automatiquement chargé lorsque vous utilisez une méthode comme `AutoModel.from_pretrained("model_output/")`.

## 2. `model_output/label_mapping.json`

Le fichier `label_mapping.json` est un fichier auxiliaire qui contient spécifiquement la correspondance entre les noms des classes (les chroniques) et leurs identifiants numériques.

### Rôles principaux :
- **Source de vérité pour les labels** : Bien que ces informations soient également présentes dans `config.json`, ce fichier indépendant facilite l'accès au mapping pour des scripts personnalisés qui n'auraient pas besoin de charger toute la configuration du modèle.
- **Persistance du mapping** : Il garantit que l'ordre des classes reste consistant entre les phases d'entraînement, d'évaluation et de prédiction.
- **Compatibilité** : Utilisé par certains scripts du projet (comme `predict.py` ou `train.py`) pour initialiser correctement la couche de classification du modèle.

---
*Note : Il est crucial que ces deux fichiers restent synchronisés. Toute modification manuelle du mapping dans l'un doit être reportée dans l'autre pour éviter des erreurs d'interprétation des résultats.*
