# Analyse de l'échec de détection des chroniques

L'absence de détection de chroniques par la fonction `predict` (résultat `[]` ou absence de logs de détection) s'explique par plusieurs facteurs structurels identifiés dans les données d'entraînement et la configuration du modèle.

## 1. Paradoxe du déséquilibre des classes

Bien que les chroniques représentent **99,23%** des segments, ce chiffre est trompeur pour l'apprentissage :
- **Dilution** : Ces 38 521 segments sont répartis sur **plus de 75 classes différentes**. En moyenne, chaque chronique ne dispose que d'environ **500 segments** (soit environ 80 minutes de son cumulé).
- **Faiblesse du "Background"** : Avec seulement **298 segments (0,77%)**, la classe `background` est massivement sous-représentée. Le modèle n'a pas assez d'exemples de "ce qui n'est pas une chronique" (silence, publicité, musique, transitions) pour apprendre à les rejeter.
- **Résultat** : Le modèle est incapable de se forger une signature acoustique forte pour chaque classe et finit par produire des probabilités quasi-uniformes (autour de 0,01-0,02 par classe).

## 2. Incohérence des Labels (Désynchronisation)

Une analyse des fichiers de sortie montre une déconnexion entre le modèle et son mapping :
- Le fichier `model_output/config.json` contient **100 labels**, incluant des doublons non nettoyés (ex: `angle-eco` vs `angle_eco`).
- Le fichier `label_mapping.json` contient **77 labels**.
- Les indices ne correspondent pas. Par exemple, l'indice **3** est `angle_eco` dans la config du modèle, mais correspondrait à `background` dans le mapping souhaité.
- Cette confusion suggère que le modèle a été entraîné ou sauvé sur une base de labels différente de celle attendue, ce qui fausse les prédictions et les filtres de `predict.py`.

## 3. Seuil de confiance trop restrictif

Dans `predict.py`, le seuil par défaut est à **0.4** (`threshold=0.4`). 
- Or, les tests sur les probabilités brutes montrent que le modèle ne dépasse jamais **0.02** de confiance sur les segments testés.
- Comme aucune classe ne dépasse 0.4, toutes les détections potentielles sont filtrées avant même d'être affichées.

## 4. Stratégie de Segmentation

L'entraînement utilise des segments de **10 secondes** échantillonnés toutes les **5 secondes**. 
- Si une chronique dure 3 minutes, elle génère beaucoup de segments de parole qui se ressemblent entre les différentes émissions.
- Les éléments les plus discriminants (les jingles) ne représentent qu'une infime fraction des données.
- Sans une pondération spécifique ou une attention particulière aux jingles, le modèle se perd dans la similarité des voix.

## Solutions préconisées

1.  **Rééquilibrer le dataset** : Augmenter massivement le nombre de segments de `background` (viser au moins 20-30% du total) pour que le modèle apprenne à dire "Je ne sais pas".
2.  **Nettoyer les labels** : Supprimer le dossier `model_output` et relancer un entraînement propre pour s'assurer que `config.json` et `label_mapping.json` sont parfaitement alignés.
3.  **Ajuster le seuil** : Pour le debug, baisser le `threshold` à **0.05** dans `predict.py` pour voir ce que le modèle "hésite" à prédire.
4.  **Data Augmentation** : Ajouter du bruit et des variations de volume aux chroniques pour forcer le modèle à extraire des caractéristiques plus robustes que la simple signature sonore d'un enregistrement spécifique.
5.  **Utiliser un Class Weighter** : Modifier `train.py` pour passer des `compute_class_weights` au Trainer afin de compenser la rareté du `background`.
