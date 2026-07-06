# Méthodologie d'Évaluation de la Détection de Chroniques

Cet article détaille la méthodologie appliquée par le programme `main.py` pour évaluer et comparer objectivement différentes méthodes de détection de chroniques dans un flux audio.

## 1. Objectif du Framework
L'objectif est de fournir un banc d'essai unifié capable de mesurer les performances de diverses approches (Intelligence Artificielle, Machine Learning, Traitement du Signal) selon des critères standardisés de précision temporelle et de réactivité.

## 2. Architecture du Système d'Évaluation

Le framework repose sur trois piliers :
*   **Les résultats** : Le système supporte l'injection directe de fichiers JSON (contenant `label`, `start`, `end`, `detected_at` et `confidence`) pour évaluer des résultats calculés dans par différentes méthodes.
*   **La Vérité Terrain (`ground_truth/`)** : Un fichier de référence (JSON) contenant les horodatages exacts (début et fin) de chaque chronique réelle.
*   **L'Évaluateur (`evaluator.py`)** : Le moteur de calcul qui compare les prédictions (issues du simulateur ou d'un JSON) aux données réelles.

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

### D. Évaluation Label-Agnostic
Le framework propose un mode **Label-Agnostic**. Lorsqu'il est activé, l'évaluateur ignore le type de chronique (le label) pour se concentrer uniquement sur la détection temporelle. 
*   **Utilité** : Évaluer la capacité d'un algorithme à détecter *l'occurrence* d'une chronique, indépendamment de sa classification correcte.
*   **Fonctionnement** : Une détection est validée si elle chevauche n'importe quelle chronique de la vérité terrain avec un IoU suffisant (> 0.3), même si leurs labels diffèrent.
*   **Usage par défaut** : Ce mode est automatiquement activé pour certaines méthodes comme `live_transcription`.

## 4. Calcul du Score Global (Overall Score)

Pour faciliter la comparaison entre les méthodes, un score sur 100 est calculé selon la pondération suivante :

1.  **Composante IoU (60%)** : Reflète la précision du fenêtrage temporel.
2.  **Composante Latence (40%)** : Récompense la rapidité de détection.
    *   Un bonus maximal est accordé pour une latence < 5s.
    *   Le score décroît linéairement jusqu'à 60s de latence, au-delà de laquelle le score de latence est de 0.

**Formule :** `Score = (Moyenne_IoU * 0.6 + Score_Latence * 0.4) * 100`

## 5. Fonctionnement du Programme `main.py`

Le script principal orchestre l'évaluation en se focalisant sur le traitement des fichiers de résultats :

1.  **Préparation** : Les outils de détection externes génèrent leurs prédictions au format JSON.
2.  **Injection** : Le programme `main.py` charge ces fichiers ainsi que la vérité terrain correspondante. Le flag `--label-agnostic` peut être passé pour ignorer la comparaison des labels.
3.  **Analyse** : L'évaluateur compare les deux jeux de données et calcule les scores (IoU, Latence, F1).
4.  **Rapport** : Génération d'un résumé détaillé (`results_[methode].json`) et mise à jour automatique de la matrice comparative globale (`evaluation_matrix.csv`).

*Note : Les anciens modes de simulation "temps réel" via wrappers sont conservés de manière transitoire mais ne constituent plus la cible privilégiée du framework.*

## Conclusion

Cette méthodologie permet de mettre en lumière le compromis "Précision vs Réactivité". Par exemple, une approche basée sur un LLM "Global" pourra être très précise sur les limites temporelles mais avoir une latence élevée, tandis qu'une méthode audio légère pourra être quasi instantanée au prix d'une précision moindre.
égère pourra être quasi instantanée au prix d'une précision moindre.
