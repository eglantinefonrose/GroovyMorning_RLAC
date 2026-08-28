# Le Cheminement de l'Entraînement des Modèles Texte pour la Détection de Chroniques

Cet article retrace l'évolution technique et les étapes méthodologiques suivies pour entraîner des modèles capables de détecter
automatiquement des chroniques radio en analysant le contenu textuel issu de la transcription (Speech-to-Text) des flux audio.

## Introduction : La Méthodologie Générale

La détection de segments via le texte repose sur l'analyse de séquences linguistiques. Contrairement à l'approche audio qui
s'appuie sur des textures sonores, cette méthode exploite la sémantique, la structure du discours et les marqueurs textuels
(formules d'introduction, transitions) pour isoler les chroniques au sein d'une transcription.

On a exploré trois voies majeures :
1. L'approche "Intelligence Sémantique" (LLM & Few-Shot) : Utiliser la puissance de raisonnement de modèles de langage (Mistral,
   Claude, DeepSeek) via des prompts structurés pour identifier les segments.
2. L'approche "Analyse Statistique" (Classical NLP) : Extraire des caractéristiques textuelles (TF-IDF, fenêtres glissantes) et
   utiliser des classifieurs légers comme le Random Forest.
3. L'approche "Deep Learning Sémantique" (Fine-Tuning BERT) : Spécialiser des modèles de langage français (CamemBERT) pour la
   classification de segments ou la détection précise des phrases d'amorce.

### Suivi et reproductibilité des entraînements
Pour assurer une traçabilité rigoureuse de nos expérimentations textuelles, on utilise la plateforme Weights & Biases (WandB). Cet
outil nous permet de centraliser :
- Le monitoring des métriques : suivi en temps réel de la perte (loss) et des scores de précision (F1-score) sur les labels de
  texte.
- La configuration matérielle : enregistrement des ressources utilisées pour les phases de fine-tuning.
- L'archivage des hyperparamètres : conservation des configurations (taille de fenêtre de contexte, taux d'apprentissage) pour
  identifier les architectures les plus performantes.

### Évaluation de la performance (Scoring RLAC)
La qualité des modèles textuels est soumise au même système de notation exigeant que le reste du projet RLAC :
- La Cardinalité (40%) : La capacité du modèle à ne pas manquer de chroniques et à ne pas inventer de faux segments dans le
  texte.
- L'Alignement Temporel (60%) : La précision des timecodes extraits de la transcription (SRT) pour marquer le début et la fin
  exacte de l'intervention.

### Publication et déploiement
L'ensemble des modèles de classification de texte et de détection de débuts de chroniques sont publiés sur l'espace Hugging Face
du projet.