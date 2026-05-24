# Liste des essais faits

- Finetune du modèle de facebook/wav2vec2-large-xlsr-53-french
- Modification des fichiers renseignant les timecodes des chroniques pour prendre en compte le fait que des chroniques ne sont pas détectées
- Modification de la méthode predict pour jouer sur les paramètres threshold, la durée minimale et le Gap Filling
- Essai d'entraîner les modèles avec des données contenant pas de chroniques avec des poids importants
- Essai d'entraîner le programme sans prendre en compte le nom des chroniques
- Prédiction robuste
- Prédiction smooth
- Approche hybride (essai de détecter les jingles puis de classer les choses segments suivant les jingles en chroniques ou non)
- Fine Tune de différents modèles avec des propriétés différentes
- Création d’un programme qui, à partir du résultat recherché (fichier audio avec dates de chroniques connues) teste plein de valeurs de paramètres pour trouver celles qui permettent d’obtenir le bon résultat
