# Documentation de la Prédiction avec Lissage (predict_smooth.py)

Cette version simplifiée se concentre uniquement sur le **lissage temporel par moyenne mobile** pour stabiliser les détections sans utiliser la complexité de l'hystérésis ou du score compétitif.

## Principe du Lissage (Moving Average)
Dans une prédiction classique, chaque fenêtre est traitée indépendamment. Si le modèle a une micro-hésitation, la chronique est coupée. 

L'approche "Smooth" fonctionne ainsi :
1. Elle récupère la probabilité de la classe "chronique" pour chaque fenêtre.
2. Elle applique une **moyenne glissante** sur ces probabilités.
3. Une décision est prise sur la valeur lissée par rapport à un seuil unique.

## Avantages
- **Simplicité** : Plus facile à comprendre et à régler que la version robuste.
- **Continuité** : Élimine naturellement les faux positifs très courts (pics) et comble les micro-trous au milieu des chroniques.

## Paramètres Clés
- `--threshold` : Le seuil de confiance (unique).
- `--smooth_window` : Le nombre de fenêtres à moyenner (ex: 3 ou 5). Plus ce chiffre est haut, plus la détection est "inerte" et stable.

## Utilisation
```bash
python src/predict_smooth.py path/to/audio.mp3 --threshold 0.5 --smooth_window 5
```
