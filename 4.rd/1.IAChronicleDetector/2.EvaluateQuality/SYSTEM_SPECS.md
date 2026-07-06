# Spécifications du Système de Détection et Évaluation de Chroniques

## 1. Objectif
Créer un framework unifié pour exécuter différentes méthodes de détection de chroniques radio sur un fichier audio, et évaluer leurs performances selon deux axes : l'**exactitude** (précision temporelle) et la **latence** (réactivité en conditions live).

## 2. Architecture Globale

### A. L'Orchestrateur (`main.py`)
Le point d'entrée unique.
- **Entrées :** Chemin audio, Identifiant de la méthode, Chemin de la Vérité Terrain (Ground Truth).
- **Fonctions :** 
  - Charger dynamiquement le module correspondant à la méthode choisie.
  - Initialiser l'environnement de la méthode (modèles, variables d'environnement).
  - Lancer le processus de détection.
  - Passer le résultat au moteur d'évaluation.

### B. Interface Standard des Méthodes
Chaque sous-dossier de méthode (ex: `10.DeepSeekChronicleDetector`) doit être encapsulé pour exposer une interface commune :
- **Entrée :** Un flux audio (ou un chemin de fichier avec simulation de streaming).
- **Sortie :** Un fichier JSON standardisé :
```json
[
  {
    "label": "nom_chronique",
    "start": 120.5,           // Début réel (secondes depuis le début du fichier)
    "end": 240.0,             // Fin réelle
    "detected_at": 135.2,     // Moment où le système a "confirmé" la détection
    "confidence": 0.95
  }
]
```

### C. Simulateur de Flux Live
Pour mesurer la latence réelle, le système doit simuler un flux :
- Découper l'audio en buffers de $X$ secondes.
- Envoyer ces buffers séquentiellement à la méthode de détection.
- Enregistrer le timestamp audio exact au moment où la méthode renvoie une détection positive.

## 3. Métriques d'Évaluation

### A. Score d'Exactitude (IoU - Intersection over Union)
Pour chaque chronique détectée correspondant à une chronique du Ground Truth (GT) :
- **Formule :** $IoU = \frac{\text{Intersection(Pred, GT)}}{\text{Union(Pred, GT)}}$
- **Seuil :** Une chronique est considérée comme "Trouvée" si IoU > 0.5.

### B. Score de Latence
Mesure la réactivité du système.
- **Formule :** $Latence = T_{detected\_at} - T_{start\_GT}$
- **Note :** 
  - < 5s : Excellent
  - 5s - 20s : Satisfaisant
  - > 20s : Mauvais (trop tard pour un usage live interactif)

### C. Rapport Final
Génération d'un résumé incluant :
- **Précision / Rappel** (Chroniques manquées vs Faux positifs).
- **Latence Moyenne** du système.
- **Note Globale /100** combinant IoU et Latence.

## 4. Structure des Dossiers Cible
```text
/
├── main.py                 # Orchestrateur
├── evaluator.py            # Logique de calcul des scores
├── ground_truth/           # Fichiers de référence (.json)
├── results/                # (Optionnel) Dossier pour les injections JSON
├── SYSTEM_SPECS.md         # Ce document
├── simulator.py (Legacy)   # Simulation de flux audio
└── methods/ (Legacy)       # Wrappers vers les anciens sous-projets
```

## 5. Contraintes Techniques
- Langage : Python 3.10+
- Portabilité : Les méthodes doivent pouvoir être isolées (via leurs propres `venv` ou via une gestion propre des imports).
- Logs : Garder une trace détaillée de chaque étape de détection pour le debug.
olées (via leurs propres `venv` ou via une gestion propre des imports).
- Logs : Garder une trace détaillée de chaque étape de détection pour le debug.
