from src.logic import ChronicleClassifier
import argparse
from pathlib import Path

def detect():
    parser = argparse.ArgumentParser(description="Détecte les chroniques dans un fichier audio")
    parser.add_argument("--model", required=True, help="Chemin vers le modèle .pkl")
    parser.add_argument("audio", help="Chemin vers le fichier audio à analyser")
    parser.add_argument("--no-extract", action="store_true", help="Ne pas extraire les segments en fichiers audio")
    parser.add_argument("--threshold", type=float, default=0.89, help="Seuil de détection (0.0 à 1.0)")
    args = parser.parse_args()

    if not Path(args.model).exists():
        print(f"Erreur: Modèle non trouvé: {args.model}")
        return
    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}")
        return

    classifier = ChronicleClassifier()
    classifier.load_model(args.model)
    
    print(f"Analyse de {args.audio}...")
    segments = classifier.detect_chronicles_in_file(args.audio, threshold=args.threshold, extract_segments=not args.no_extract)
    
    print(f"\nRésultats : {len(segments)} segments détectés.")
    for i, seg in enumerate(segments, 1):
        print(f"Segment #{i}: {seg['start']:.1f}s -> {seg['end']:.1f}s (Confiance: {seg['conf']:.1%})")

if __name__ == "__main__":
    detect()
