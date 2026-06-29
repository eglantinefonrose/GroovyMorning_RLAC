import torch
from transformers import CamembertTokenizer, CamembertForSequenceClassification
import re

class ChronicleDetector:
    def __init__(self, model_path="./camembert_chronicle_start"):
        """
        Initialise le détecteur avec le modèle CamemBERT entraîné.
        """
        print(f"Chargement du modèle depuis {model_path}...")
        self.tokenizer = CamembertTokenizer.from_pretrained(model_path)
        self.model = CamembertForSequenceClassification.from_pretrained(model_path)
        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

    def split_into_sentences(self, text):
        """
        Découpe un texte en phrases basées sur la ponctuation (. ! ?).
        """
        # Nettoyage basique
        text = text.replace('\n', ' ').strip()
        # Découpage sur la ponctuation de fin de phrase
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def predict_starts(self, text, threshold=0.85, group_consecutive=False):
        """
        Analyse un texte complet et renvoie les premières phrases de chaque chronique détectée.
        
        Args:
            text (str): La transcription complète de l'émission.
            threshold (float): Seuil de probabilité pour accepter un début (0.0 à 1.0).
            group_consecutive (bool): Si True, évite de renvoyer plusieurs phrases de suite 
                                     si elles sont toutes détectées comme des débuts.
        """
        sentences = self.split_into_sentences(text)
        detected_starts = []
        
        print(f"Analyse de {len(sentences)} phrases...")
        
        last_was_start = False
        
        for sentence in sentences:
            inputs = self.tokenizer(
                sentence, 
                return_tensors="pt", 
                truncation=True, 
                max_length=128
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                # probabilité de la classe 1 (DEBUT)
                prob_start = probs[0][1].item()
                
                is_start = prob_start >= threshold
                
                if is_start:
                    if not group_consecutive or not last_was_start:
                        detected_starts.append({
                            "sentence": sentence,
                            "confidence": prob_start
                        })
                    last_was_start = True
                else:
                    last_was_start = False
        
        return detected_starts

def get_chronicle_starts(text):
    """
    Fonction utilitaire pour une utilisation rapide.
    """
    detector = ChronicleDetector()
    results = detector.predict_starts(text)
    return [r["sentence"] for r in results]

def clean_srt_content(content):
    """Supprime les indices et les horodatages des fichiers SRT."""
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if '-->' in line:
            continue
        clean_lines.append(line)
    return " ".join(clean_lines)

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Détecte les débuts de chroniques dans un fichier de transcription.")
    parser.add_argument("file_path", help="Chemin vers le fichier texte (.txt ou .srt) à analyser.")
    parser.add_argument("--threshold", type=float, default=0.85, help="Seuil de confiance (0.0 à 1.0).")
    parser.add_argument("--model", default="./camembert_chronicle_start", help="Chemin vers le modèle.")
    
    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"Erreur : Le fichier '{args.file_path}' n'existe pas.")
    else:
        try:
            with open(args.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if args.file_path.lower().endswith(".srt"):
                print("Fichier SRT détecté, nettoyage en cours...")
                content = clean_srt_content(content)
                
            detector = ChronicleDetector(model_path=args.model)
            results = detector.predict_starts(content, threshold=args.threshold)
            
            print(f"\n--- Résultats pour : {os.path.basename(args.file_path)} ---")
            if not results:
                print("Aucun début de chronique détecté.")
            for i, res in enumerate(results, 1):
                print(f"{i}. [{res['confidence']:.2f}] {res['sentence']}")
                
        except Exception as e:
            print(f"Une erreur est survenue lors de la lecture du fichier : {e}")
