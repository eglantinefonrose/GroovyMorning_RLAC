## Introduction : La Méthodologie Générale

La détection de segments audio repose sur une approche de **classification de séquences**. L'idée fondamentale est de découper un flux audio continu en segments temporels et d'assigner à chaque segment une étiquette (ex: "Chronique X", "Publicité", ou "Bruit de fond").

On a exploré deux voies majeures :
1.  **L'approche "Caractérisation Acoustique" (Classical ML)** : Extraire des signatures mathématiques (MFCC, énergie) et utiliser des classifieurs classiques (Random Forest).
2.  **L'approche "Deep Learning / Fine-Tuning"** : Utiliser un modèle de reconnaissance vocale pré-entraîné (comme Wav2Vec2) et le spécialiser sur nos données spécifiques.

### Suivi et reproductibilité des entraînements
Pour assurer une traçabilité rigoureuse de nos expérimentations, on utilise la plateforme Weights & Biases (WandB). Cet outil nous permet de centraliser :
- Le monitoring des métriques : suivi en temps réel de la perte (loss) et des scores de précision (F1-score) durant l'entraînement.
- La configuration matérielle : enregistrement des caractéristiques de la machine (GPU, CPU, mémoire) pour garantir la reproductibilité des résultats.
- L'archivage des hyperparamètres : conservation de chaque configuration testée pour identifier les modèles les plus performants.

### Évaluation de la performance (Scoring RLAC)
La qualité des modèles ne se limite pas à une simple précision statistique. On a mit en place un système de notation spécifique au projet RLAC, basé sur deux critères majeurs :
- La Cardinalité (40%) : La capacité du modèle à identifier le nombre exact de chroniques présentes, sans omission ni sur-segmentation.
- L'Alignement Temporel (60%) : La précision chirurgicale des points de début et de fin de chaque chronique détectée par rapport à la réalité.

### Publication et déploiement
L'ensemble des modèles sont publiés sur l'espace Hugging Face du projet.