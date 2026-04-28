# Méthode d'Évaluation du Modèle de Détection

Ce document décrit l'algorithme utilisé pour noter la performance des modèles de détection de chroniques. L'objectif est de privilégier la structure de l'émission et la précision temporelle.

## Score Global

Le score final est une moyenne pondérée de deux indicateurs majeurs :
1. **Note de Cardinalité (40%)** : Capacité du modèle à identifier le bon nombre de chroniques.
2. **Note d'Alignement Séquentiel (60%)** : Précision du calage temporel (début/fin) pour chaque chronique.

---

## 1. Note de Cardinalité (40%)

On évalue la différence entre le nombre de chroniques prédites ($N_{pred}$) et le nombre réel ($N_{gt}$).

- **Calcul** : `max(0, 1 - abs(N_gt - N_pred) / N_gt)`
- **Logique** : 
    - Si le nombre est exact : 100% de la note.
    - Si le modèle prédit un bloc unique au lieu de 5 chroniques : la note tombe à 20%.
    - Si le modèle prédit deux fois trop de chroniques : la note tombe à 0%.

## 2. Note d'Alignement Séquentiel (60%)

On itère chronologiquement sur la vérité terrain (Ground Truth) et on cherche la prédiction correspondante.

### Processus d'appariement
Pour chaque chronique réelle $C_{gt}$ :
1. On cherche la prédiction $C_{pred}$ non encore utilisée qui maximise l'IoU (Intersection over Union).
2. Si une prédiction est trouvée avec un IoU > 0 :
    - On calcule le **décalage moyen** : `(abs(start_gt - start_pred) + abs(end_gt - end_pred)) / 2`.
    - La note de la chronique décroît linéairement avec le décalage (ex: 0% de note si décalage > 60s).
3. Si aucune prédiction ne correspond : la note de la chronique est **0**.

### Résilience
Si le modèle manque une chronique au milieu de l'émission, l'algorithme "saute" la chronique manquante (note 0) et continue l'évaluation sur la suivante pour vérifier si le modèle "retombe sur ses pattes" plus loin.

## 3. Score Individuel par Chronique (Détail)

Au-delà du score global, chaque chronique réelle ($C_{gt}$) se voit attribuer une note de précision propre, comprise entre 0 et 100%. Cette note permet d'identifier précisément quelles parties de l'émission sont les plus difficiles à détecter pour le modèle.

### Calcul de la note par segment
La note d'une chronique est calculée selon la formule de pénalité temporelle :

$$Score_{chronique} = \max\left(0, 1 - \frac{\text{Décalage Moyen}}{\text{Tolérance Max}}\right)$$

*   **Décalage Moyen** : Moyenne de l'erreur sur le début et l'erreur sur la fin $|start_{diff}| + |end_{diff}| / 2$.
*   **Tolérance Max** : Seuil au-delà duquel la détection est jugée inutile (par défaut 60 secondes).

### Statuts de détection
Chaque chronique est ensuite classée selon son score :
- **Parfaite** : Score > 95% (Décalage < 3s).
- **Acceptable** : Score entre 70% et 95% (Décalage < 18s).
- **Imprécise** : Score entre 1% et 70% (Décalage < 60s).
- **Manquante (Miss)** : Score = 0% (Aucun segment trouvé ou décalage > 60s).

---

## 4. Export des résultats

Les résultats sont exportés dans `results/evaluation_results.csv` avec :
- Le détail par chronique (Décalage, IoU, Statut).
- Une ligne de résumé contenant le Score Global pondéré.
