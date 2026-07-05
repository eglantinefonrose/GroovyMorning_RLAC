# Framework d'Évaluation de Détection de Chroniques

Ce dossier contient le framework unifié pour évaluer différentes méthodes de détection de chroniques radio.

## Structure
- `main.py` : Orchestrateur du processus d'évaluation.
- `evaluator.py` : Logique de calcul des métriques (IoU, Latence, Précision, Rappel).
- `simulator.py` : Simulation de flux audio pour la mesure de latence.
- `methods/` : Wrappers standardisés pour chaque méthode de détection.
- `ground_truth/` : Fichiers JSON de référence.

## Utilisation
Pour lancer une évaluation :
```bash
python main.py --audio chemin/vers/audio.mp3 --method deepseek --gt ground_truth/ref.json
```

## Ajout d'une Méthode
Créez un fichier `methods/[nom]_wrapper.py` contenant une classe `Wrapper` avec la méthode :
```python
def process_stream(self, audio_path, buffer_size_seconds):
    # ... logique de détection ...
    return [
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
