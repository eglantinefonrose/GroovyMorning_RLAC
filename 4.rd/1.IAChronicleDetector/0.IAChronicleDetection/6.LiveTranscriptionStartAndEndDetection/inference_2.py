import torch
from transformers import CamembertTokenizer, CamembertForSequenceClassification
import re

class ChronicleDetectorV2:
    def __init__(self, model_path="./camembert_chronicle_start"):
        """
        Initialise le détecteur V2 (basé sur le contexte multi-phrases).
        """
        print(f"Chargement du modèle V2 depuis {model_path}...")
        self.tokenizer = CamembertTokenizer.from_pretrained(model_path)
        self.model = CamembertForSequenceClassification.from_pretrained(model_path)
        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

    def split_into_sentences(self, text):
        """Découpage du texte en phrases."""
        text = text.replace('\n', ' ').strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def predict_starts(self, text, threshold=0.8, window_size=3):
        """
        Analyse le texte avec une fenêtre glissante pour capturer le contexte.
        """
        sentences = self.split_into_sentences(text)
        detected_starts = []
        
        print(f"Analyse de {len(sentences)} phrases avec fenêtre de {window_size}...")
        
        for i in range(len(sentences)):
            # On construit le contexte (phrases i à i + window_size)
            context = " ".join(sentences[i : i + window_size])
            
            inputs = self.tokenizer(
                context, 
                return_tensors="pt", 
                truncation=True, 
                max_length=256
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                prob_start = probs[0][1].item()
                
                if prob_start >= threshold:
                    detected_starts.append({
                        "sentence": sentences[i], # On renvoie la phrase exacte de début
                        "context": context,        # Et le contexte qui a servi à décider
                        "confidence": prob_start,
                        "index": i,
                        "preview": " ".join(sentences[i : i + 3])
                    })
        
        # Post-processing : si plusieurs phrases consécutives sont détectées,
        # on ne garde que la première (le vrai "déclencheur")
        final_starts = []
        if detected_starts:
            final_starts.append(detected_starts[0])
            for j in range(1, len(detected_starts)):
                # Si l'écart entre deux détections est > 5 phrases, c'est une nouvelle chronique
                if detected_starts[j]["index"] > detected_starts[j-1]["index"] + 5:
                    final_starts.append(detected_starts[j])
                    
        return final_starts

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("file_path")
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--model", default="./camembert_chronicle_start_v4")
    
    args = parser.parse_args()

    if os.path.exists(args.file_path):
        with open(args.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        detector = ChronicleDetectorV2(model_path=args.model)
        results = detector.predict_starts(content, threshold=args.threshold)
        
        print(f"\n--- Détections (Modèle V2) ---")
        for res in results:
            print(f"[{res['confidence']:.2f}] Début détecté à : {res['sentence']}")
            print(f"   3 premières phrases : {res['preview']}")
            print(f"   Contexte de décision : {res['context']}\n")
