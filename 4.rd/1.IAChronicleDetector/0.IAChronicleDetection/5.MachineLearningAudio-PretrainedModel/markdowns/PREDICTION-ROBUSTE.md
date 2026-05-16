# Documentation de la Prédiction Robuste (predict_robust.py)

Ce document détaille les améliorations apportées au système de détection des chroniques pour résoudre les problèmes de fragmentation ("demi-chroniques") et d'instabilité des détections.

## 1. Problématique Initiale
Le script `predict.py` d'origine prenait des décisions indépendantes par fenêtre de temps. Si une seule fenêtre au milieu d'une chronique obtenait un score de confiance légèrement inférieur au seuil, la chronique était coupée en deux ou ignorée.

## 2. Améliorations Techniques

### A. Lissage par Score Compétitif (Soft Voting)
Au lieu de simplement prendre la probabilité de la classe "chronique", le script calcule un score pondéré :
- Si `prob_chronique > prob_background`, le score est égal à `prob_chronique`.
- Si `prob_background >= prob_chronique`, le score de chronique est divisé par deux.
Cela force le score à chuter drastiquement dès que le modèle commence à pencher vers le bruit de fond, créant ainsi des séparations nettes entre deux chroniques.

### B. Seuil à Hystérésis (Double Seuil)
L'utilisation d'un seuil unique crée des oscillations. Nous utilisons désormais deux seuils :
- **Seuil d'Activation (`threshold_start`)** : Un score élevé (ex: 0.7) est nécessaire pour *déclencher* le début d'une chronique.
- **Seuil de Maintien (`threshold_end`)** : Un score plus bas (ex: 0.3) suffit pour *continuer* la détection.

### C. Segmentation Précise
La fin d'un segment est désormais calculée de manière plus fine pour éviter que les chroniques ne "débordent" trop sur le silence suivant.

### D. Gestion du "Gap Filling" Intelligent
La fusion des segments est maintenant plus robuste car elle s'appuie sur une courbe de probabilité continue plutôt que sur des blocs de 10 secondes rigides.

## 3. Nouveaux Paramètres
- `--threshold_start` : Seuil pour démarrer une détection (par défaut 0.7).
- `--threshold_end` : Seuil pour maintenir une détection (par défaut 0.3).
- `--smooth_window` : Taille de la fenêtre de lissage (nombre de segments à moyenner).

## 4. Comment l'utiliser
```bash
python src/predict_robust.py path/to/audio.mp3 --model_type ast --threshold_start 0.6 --threshold_end 0.3
```
