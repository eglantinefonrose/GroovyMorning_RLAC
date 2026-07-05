import argparse
import json
import sys
import os
from pathlib import Path
import torch
import librosa
import numpy as np

# On réutilise la logique de src/predict.py mais simplifiée pour l'interface standard
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from predict import predict as predict_internal

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche Audio Pretrained)")
    parser.add_argument("audio", help="Chemin vers le fichier audio")
    parser.add_argument("--model-type", default="ast", choices=["ast", "beats", "wav2vec2"], help="Type de modèle")
    parser.add_argument("--model-dir", help="Répertoire du modèle (optionnel)")
    parser.add_argument("--threshold", type=float, default=0.4, help="Seuil de confiance")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)

    # Détermination du répertoire du modèle par défaut si non fourni
    model_dir = args.model_dir
    if not model_dir:
        if args.model_type == "ast":
            model_dir = "model_output_ast"
        elif args.model_type == "beats":
            model_dir = "model_output_beats"
        elif args.model_type == "wav2vec2":
            model_dir = "model_output_facebook-wav2vec2-large-xlsr-53-french"

    results_formatted = predict_internal(
        audio_path=args.audio,
        model_type=args.model_type,
        model_dir=model_dir,
        threshold=args.threshold
    )
    
    # Conversion du format HH:MM:SS en secondes pour la cohérence
    def hms_to_seconds(hms):
        parts = hms.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    standard_results = []
    for res in results_formatted:
        standard_results.append({
            "start": round(hms_to_seconds(res["start"]), 2),
            "end": round(hms_to_seconds(res["end"]), 2),
            "label": "chronique",
            "confidence": res["confidence"]
        })
    
    print(json.dumps(standard_results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
