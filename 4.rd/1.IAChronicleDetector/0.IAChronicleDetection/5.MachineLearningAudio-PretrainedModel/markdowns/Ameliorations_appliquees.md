# Liste d'améliorations appliquées pour affiner la détection des chroniques

1. Détecter juste une chronique, pas son nom  
-> Création d'une méthode "train_without_names.py" qui fine-tune un modèle sans prendre en compte le nom des chroniques.


2. Créer d'autres données où on prend uniquement les données de background  
-> Programme qui prend en compte pas toutes les chroniques mais + de données de background.

3. Uniformiser les noms des chroniques (ex: angle-eco vs angle_eco)

4. Comprendre pourquoi incohérences entre model_output/config.json et model_output/label_mapping.json.  
-> Supprimer le dossier model_output et relancer un entraînement propre pour s'assurer que config.json et label_mapping.json sont parfaitement alignés.

5. Régler soucis jingles et background trop peu présents (pondération faible)
-> Modifier train.py pour passer des compute_class_weights au Trainer afin de compenser la rareté du background