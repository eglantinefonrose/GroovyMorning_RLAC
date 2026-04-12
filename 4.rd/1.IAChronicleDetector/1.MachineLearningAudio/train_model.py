from src.logic import AdvertisementClassifier, TrainingFile, TrainingConfig
from pathlib import Path
import argparse

def train():
    parser = argparse.ArgumentParser(description="Entraîne le modèle de détection de chroniques")
    parser.add_argument("--config", default="src/training_config.txt", help="Fichier de configuration")
    parser.add_argument("--output", default="models/rlac-audio-segmenter-chroniques_model.pkl", help="Nom du modèle de sortie")
    parser.add_argument("--model-type", default="random_forest", choices=["random_forest", "svm", "mlp"], help="Type de modèle")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Erreur: Fichier de configuration non trouvé: {args.config}")
        return

    training_files = []
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            parts = line.split('|')
            if len(parts) >= 2:
                training_files.append(TrainingFile(parts[0].strip(), parts[1].strip(), parts[2].strip() if len(parts) >= 3 else ""))

    if not training_files:
        print("Aucun fichier valide trouvé dans la configuration.")
        return

    print(f"Démarrage de l'entraînement avec {len(training_files)} fichiers...")
    classifier = AdvertisementClassifier(model_type=args.model_type)
    classifier.train_from_multiple_files(training_files)
    
    Path("models").mkdir(exist_ok=True)
    classifier.save_model(args.output)
    print(f"Modèle sauvegardé dans {args.output}")

if __name__ == "__main__":
    train()
