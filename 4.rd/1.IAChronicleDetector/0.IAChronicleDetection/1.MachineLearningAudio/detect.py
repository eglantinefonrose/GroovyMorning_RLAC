import argparse
import json
import sys
from pathlib import Path
from src.logic import ChronicleClassifier

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques dans un fichier audio (Approche ML Audio)")
    parser.add_argument("audio", help="Chemin vers le fichier audio à analyser")
    parser.add_argument("--model", default="models/rlac-audio-segmenter-chroniques_model.pkl", help="Chemin vers le modèle .pkl")
    parser.add_argument("--threshold", type=float, default=0.89, help="Seuil de détection (0.0 à 1.0)")
    args = parser.parse_args()

    if not Path(args.model).exists():
        print(f"Erreur: Modèle non trouvé: {args.model}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)

    classifier = ChronicleClassifier()
    classifier.load_model(args.model)
    
    # On désactive l'extraction de segments pour le script de détection standard
    segments = classifier.detect_chronicles_in_file(args.audio, threshold=args.threshold, extract_segments=False)
    
    # Formatage de la sortie en JSON
    results = []
    for seg in segments:
        results.append({
            "start": round(seg['start'], 2),
            "end": round(seg['end'], 2),
            "label": "chronique",
            "confidence": round(seg['conf'], 3)
        })
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
