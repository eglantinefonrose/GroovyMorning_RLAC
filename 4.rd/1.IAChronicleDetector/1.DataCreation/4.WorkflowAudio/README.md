# Workflow Audio - Orchestration

Ce dossier contient les scripts permettant d'automatiser la chaîne de récupération et de traitement des chroniques radio.

## Scripts de Workflow

### 1. `run_download_workflow.py`
**Rôle : Téléchargement automatisé.**
Ce script sert d'interface globale pour télécharger les émissions de plusieurs stations (France Inter, France Info, France Culture, RTL).
- Il prend en entrée une plage de dates au format `DD-MM-YYYY`.
- Il appelle les scripts de téléchargement spécifiques à chaque radio situés dans le dossier parent.

### 2. `run_audio_workflow.py`
**Rôle : Découpage et nettoyage (Trimming).**
Ce script traite les fichiers audio téléchargés pour n'en garder que les segments pertinents définis par des timecodes.
- **Logique intelligente** : Il conserve les transitions courtes (moins de 2 minutes) pour maintenir la fluidité.
- **Sorties** : Génère un fichier audio `_trimmed` et un nouveau fichier de timecodes recalibrés dans un dossier `news`.
- **Arguments** : Accepte `--start` et `--end` (format `YYYY-MM-DD`), ainsi que `--force` pour réécrire les fichiers.

### 3. `run_full_workflow.py`
**Rôle : Orchestrateur complet.**
C'est le point d'entrée principal qui enchaîne les deux étapes précédentes.
1. Il lance `run_download_workflow.py` pour récupérer les fichiers manquants.
2. Il lance ensuite `run_audio_workflow.py` pour effectuer le découpage.
- Il gère la conversion des formats de date entre les deux sous-scripts.

---

## Utilisation rapide

Pour lancer le workflow complet sur une période donnée :
```bash
python run_full_workflow.py 20-05-2026 25-05-2026
```

Pour simplement traiter l'audio (sans télécharger) :
```bash
python run_audio_workflow.py --start 2026-05-20 --end 2026-05-25
```
