# Approche Hybride : Détection par Jingles (Landmarks)

Cette approche vise à résoudre les problèmes de précision de début de chronique en utilisant les **jingles d'introduction** comme points d'ancrage de haute confiance.

## 1. Concept

Plutôt que d'essayer de classer chaque segment de 10 secondes comme "chronique" ou "background" avec un seul modèle, ce qui crée souvent des ambiguïtés aux frontières, l'approche hybride divise le problème en deux étapes :

1.  **Détection de Jingle :** Rechercher le motif sonore court et spécifique qui annonce le début d'une chronique.
2.  **Extension de Chronique :** Une fois le début "ancré" par un jingle, utiliser le modèle de chronique général pour suivre la parole jusqu'à sa fin naturelle.

---

## 2. Entraînement du Modèle de Jingle (`src/train/train_jingle.py`)

Le script d'entraînement crée un modèle binaire (Jingle vs Background) optimisé pour les signatures acoustiques.

### Logique d'échantillonnage
*   **Classe `jingle` (Positifs) :** Le script extrait uniquement les **5 premières secondes** de chaque chronique définie dans les timecodes. C'est là que se trouve généralement la signature musicale ou sonore de l'émission.
*   **Classe `background` (Négatifs) :**
    *   Segments de silence ou musique entre les chroniques.
    *   Segments prélevés au **milieu** des chroniques (après le jingle). Cela apprend au modèle à faire la distinction entre "le jingle de la chronique" et "la parole de la chronique".

### Modèle utilisé
Utilise **AST (Audio Spectrogram Transformer)** (`MIT/ast-finetuned-audioset`), car sa capacité à analyser l'audio comme une image (via spectrogrammes) est supérieure pour reconnaître des motifs musicaux répétitifs comme les jingles.

### Commande
```bash
./.venv/bin/python3 src/train/train_jingle.py --epochs 5
```
Le modèle est sauvegardé dans `./model_output_jingle`.

---

## 3. Inférence Hybride (`src/predict_hybrid.py`)

Ce script combine les deux modèles pour une segmentation précise.

### Algorithme
1.  **Scan (Pas de 1s) :** Le script parcourt l'audio avec le modèle de **Jingle**. Comme le pas est court (1s), on obtient une précision chirurgicale sur le début.
2.  **Détection :** Si la probabilité de Jingle dépasse le seuil (ex: 0.8), un point d'ancrage est créé.
3.  **Suivi (Tracking) :** À partir de ce point, le script bascule sur le modèle de **Chronique** général. Il avance par bonds de 5s pour vérifier si le contenu est toujours une chronique.
4.  **Fin de segment :** La fin est marquée dès que le modèle de chronique renvoie une confiance faible sur une durée prolongée (15s par défaut).
5.  **Reprise :** Le scan de jingles reprend après la fin de la chronique détectée.

### Avantages
*   **Débuts précis :** Plus de décalage de 5 ou 10 secondes au début.
*   **Robustesse :** Réduit drastiquement les faux positifs au milieu des émissions, car une chronique n'est validée que si elle commence par un jingle.
*   **Séparation :** Permet de mieux séparer deux chroniques qui s'enchaînent si elles ont des jingles distincts.

### Commande
```bash
./.venv/bin/python3 src/predict_hybrid.py chemin/vers/audio.mp3 \
    --jingle_threshold 0.8 \
    --chronicle_threshold 0.5 \
    --output resultat_hybride.json
```

---

## 4. Paramètres Clés

| Paramètre | Description |
| :--- | :--- |
| `--jingle_threshold` | Sensibilité de la détection du jingle. Un seuil haut (0.8+) évite les faux déclenchements. |
| `--chronicle_threshold` | Seuil de maintien de la chronique. Peut être plus bas (0.5) pour éviter les coupures lors de silences durant la chronique. |
| `JINGLE_DURATION` | Fixée à 5s dans l'entraînement. Doit correspondre à la durée moyenne des jingles cibles. |
