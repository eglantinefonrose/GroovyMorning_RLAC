# Framework d'Évaluation de Détection de Chroniques

Ce dossier contient le framework unifié pour évaluer différentes méthodes de détection de chroniques radio.

## Structure
- `main.py` : Orchestrateur du processus d'évaluation.
- `evaluator.py` : Logique de calcul des métriques (IoU, Latence, Précision, Rappel).
- `ground_truth/` : Fichiers JSON de référence.
- `methods/` (Legacy) : Wrappers pour l'exécution directe des modèles.
- `simulator.py` (Legacy) : Simulation de flux audio pour la mesure de latence.

## Utilisation
Le framework privilégie désormais l'injection directe de fichiers de résultats pré-calculés au format JSON.

```bash
# Évaluation via fichier de résultats JSON
python main.py --results results_ma_methode.json --gt ground_truth/ref.json
```

## Injection de Résultats
Chaque méthode doit produire un fichier JSON contenant une liste de détections :
```json
[
  {
    "label": "nom_chronique",
    "start": 10.0,
    "end": 60.0,
    "detected_at": 15.0,
    "confidence": 0.95
  }
]
```

## Métriques
- **IoU (Intersection over Union)** : Mesure la précision temporelle du segment détecté. Seuil de succès > 0.5.
- **Latence** : Différence entre le moment de la détection (`detected_at`) et le début réel de la chronique.
- **Score Global** : Combinaison pondérée de l'IoU et de la Latence.

