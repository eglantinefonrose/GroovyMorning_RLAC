# Méthodologie d'Évaluation de la Détection de Chroniques

Cet article détaille la méthodologie appliquée par le programme `main.py` pour évaluer et comparer objectivement différentes méthodes de détection de chroniques dans un flux audio.

## 1. Objectif du Framework
L'objectif est de fournir un banc d'essai unifié capable de mesurer les performances de diverses approches (Intelligence Artificielle, Machine Learning, Traitement du Signal) selon des critères standardisés de précision temporelle et de réactivité.

## 2. Architecture du Système d'Évaluation

Le framework repose sur quatre piliers :
*   **Les Wrappers (`methods/`)** : Des interfaces standardisées qui encapsulent chaque modèle. Qu'il s'agisse d'un LLM (Claude, DeepSeek), d'un modèle audio pré-entraîné ou d'une forêt aléatoire, chaque méthode expose la même API pour traiter un flux.
*   **Le Simulateur (`simulator.py`)** : Il simule une écoute "temps réel" en découpant le fichier audio en segments temporels (buffers) de taille fixe (ex: 5 secondes).
*   **La Vérité Terrain (`ground_truth/`)** : Un fichier de référence (JSON) contenant les horodatages exacts (début et fin) de chaque chronique réelle.
*   **L'Évaluateur (`evaluator.py`)** : Le moteur de calcul qui compare les prédictions aux données réelles.

## 3. Métriques de Performance

Le système ne se contente pas de vérifier si une chronique a été détectée ; il analyse la qualité de la détection sur plusieurs dimensions :

### A. Fidélité Temporelle (IoU)
Le **Intersection over Union (IoU)** mesure le chevauchement entre la période détectée par l'algorithme et la période réelle de la chronique.
*   Une valeur de **1.0** indique une superposition parfaite.
*   Le framework considère une détection comme valide si son IoU est supérieur à **0.5**.

### B. Précision, Rappel et F1-Score
*   **Précision** : Capacité de l'algorithme à ne pas générer de fausses alertes (fausses chroniques détectées).
*   **Rappel (Recall)** : Capacité de l'algorithme à détecter toutes les chroniques présentes dans le fichier.
*   **F1-Score** : Moyenne harmonique des deux, offrant une vue équilibrée de la performance globale.

### C. Latence
La latence est le délai entre le début réel d'une chronique et le moment où le système confirme sa détection. C'est un paramètre critique pour les applications en direct.

## 4. Calcul du Score Global (Overall Score)

Pour faciliter la comparaison entre les méthodes, un score sur 100 est calculé selon la pondération suivante :

1.  **Composante IoU (60%)** : Reflète la précision du fenêtrage temporel.
2.  **Composante Latence (40%)** : Récompense la rapidité de détection.
    *   Un bonus maximal est accordé pour une latence < 5s.
    *   Le score décroît linéairement jusqu'à 60s de latence, au-delà de laquelle le score de latence est de 0.

**Formule :** `Score = (Moyenne_IoU * 0.6 + Score_Latence * 0.4) * 100`

## 5. Fonctionnement du Programme `main.py`

Le script principal orchestre l'évaluation en suivant ces étapes :
1.  **Chargement** de la vérité terrain et de la méthode demandée.
2.  **Simulation** : Le flux est passé au wrapper par morceaux.
3.  **Collecte** : Chaque détection est enregistrée avec son timestamp de détection (`detected_at`).
4.  **Analyse** : L'évaluateur fait correspondre les détections aux chroniques réelles.
5.  **Rapport** : Génération d'un résumé statistique et d'un fichier JSON détaillé (`results_[methode].json`).

## Conclusion

Cette méthodologie permet de mettre en lumière le compromis "Précision vs Réactivité". Par exemple, une approche basée sur un LLM "Global" pourra être très précise sur les limites temporelles mais avoir une latence élevée, tandis qu'une méthode audio légère pourra être quasi instantanée au prix d'une précision moindre.
