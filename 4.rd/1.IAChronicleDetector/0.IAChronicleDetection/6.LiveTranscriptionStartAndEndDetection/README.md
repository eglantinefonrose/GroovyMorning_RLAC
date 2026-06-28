# Live Transcription Start Detection (CamemBERT)

Ce projet utilise un modèle **CamemBERT** (via Hugging Face Transformers) pour détecter automatiquement le début des chroniques au sein de transcriptions d'émissions de radio (STT).

## 📋 Description

L'objectif est d'identifier les phrases qui marquent l'ouverture d'une séquence spécifique (revue de presse, météo, billet d'humeur, etc.) dans un flux textuel continu.

## 🛠 Installation

Le projet nécessite Python 3.8+ et les bibliothèques suivantes :

```bash
pip install torch transformers pandas scikit-learn accelerate
```

*Note : Sur Mac avec puce Apple Silicon, l'accélération matérielle (MPS) est automatiquement utilisée.*

## 🚀 Entraînement du modèle

Le script `train_camembert.py` permet d'entraîner le modèle sur vos propres données.

1.  **Données** : Le script cherche des fichiers `.txt` dans des dossiers structurés par labels (positifs pour les débuts, négatifs pour le reste).
2.  **Lancement** :
    ```bash
    python3 train_camembert.py
    ```
3.  **Sortie** : Le modèle entraîné est sauvegardé dans le dossier `./camembert_chronicle_start`.

## 🔍 Inférence (Prédiction)

Le script `inference.py` permet d'analyser de nouvelles transcriptions.

### Utilisation en ligne de commande

Vous pouvez passer un fichier texte en paramètre pour détecter les débuts de chroniques :

```bash
python3 inference.py ma_transcription.txt
```

#### 📊 Comprendre la sortie
Le script affiche une liste numérotée des phrases identifiées comme étant des débuts de chronique :
*   **[0.XX]** : Le score de confiance (de 0.00 à 1.00). Plus le score est proche de 1.00, plus le modèle est certain qu'il s'agit d'un début de chronique.
*   **Texte** : La phrase exacte extraite de la transcription qui a déclenché la détection.

Exemple de sortie :
```text
1. [0.99] Il est 8 heures, voici le flash de l'information.
2. [0.97] On se retrouve maintenant pour la chronique environnement.
```

**Options :**
*   `--threshold` : Seuil de confiance (par défaut 0.85). Augmentez-le pour réduire les faux positifs, baissez-le si le modèle rate des débuts évidents.
*   `--model` : Chemin vers le modèle entraîné (par défaut `./camembert_chronicle_start`).

### Utilisation comme bibliothèque Python

Vous pouvez intégrer le détecteur dans vos propres scripts pour récupérer des objets structurés :

```python
from inference import ChronicleDetector

detector = ChronicleDetector("./camembert_chronicle_start")
# predict_starts renvoie une liste de dictionnaires
results = detector.predict_starts("Transcription complète...")

for res in results:
    # Chaque résultat contient :
    # - res['sentence'] : la phrase détectée
    # - res['confidence'] : le score de probabilité
    print(f"Début détecté : {res['sentence']} ({res['confidence']:.2f})")
```

### Comparer l'inférence avec le ground truth
```
python3 visualize_detection.py "../../../@assets/3.modelEvaluationData/france-inter/27-05-2026_transcription.txt" "../../../@assets/3.modelEvaluationData/france-inter/ground_truth_chroniques_start_transcriptions.txt" --output rapport_france_inter.html
```

## 🌐 Intégrations

*   **WandB** : Les métriques sont suivies en temps réel sur le projet `IAChronicleDetection`.
*   **Hugging Face Hub** : À la fin de chaque entraînement, le modèle est automatiquement publié sur [eglantinefonrose/camembert-chronicle-start-detection](https://huggingface.co/eglantinefonrose/camembert-chronicle-start-detection).

## 📂 Structure du projet

*   `train_camembert.py` : Script d'entraînement (Fine-tuning de CamemBERT).
*   `inference.py` : Script et classe utilitaire pour la détection sur de nouveaux textes.
*   `camembert_chronicle_start/` : Dossier contenant le modèle entraîné (généré après l'entraînement).
