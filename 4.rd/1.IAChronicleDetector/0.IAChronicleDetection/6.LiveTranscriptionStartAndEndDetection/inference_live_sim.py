import torch
from transformers import CamembertTokenizer, CamembertForSequenceClassification
import re
import time
import argparse
import os

class LiveChronicleDetector:
    def __init__(self, model_path="./camembert_chronicle_start_v2", window_size=3, threshold=0.8, min_gap=5):
        """
        Simulateur de détection en temps réel.
        
        Args:
            model_path: Chemin du modèle.
            window_size: Nombre de phrases nécessaires pour prendre une décision.
            threshold: Seuil de probabilité.
            min_gap: Nombre minimum de phrases entre deux détections.
        """
        print(f"Initialisation du moteur live (modèle: {model_path})...")
        self.tokenizer = CamembertTokenizer.from_pretrained(model_path)
        self.model = CamembertForSequenceClassification.from_pretrained(model_path)
        self.device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()
        
        self.window_size = window_size
        self.threshold = threshold
        self.min_gap = min_gap
        
        # État interne du flux
        self.sentence_buffer = []
        self.total_sentences_processed = 0
        self.last_detection_index = -min_gap - 1

    def split_into_sentences(self, text):
        """Découpage du texte en phrases (identique aux autres versions)."""
        text = text.replace('\n', ' ').strip()
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def process_new_sentence(self, sentence):
        """
        Traite une nouvelle phrase arrivant du flux live.
        Renvoie un dictionnaire si un début est détecté à cette phrase, sinon None.
        """
        self.sentence_buffer.append(sentence)
        self.total_sentences_processed += 1
        
        # On a besoin d'assez de phrases pour remplir la fenêtre
        if len(self.sentence_buffer) < self.window_size:
            return None
            
        # On analyse la fenêtre actuelle (les window_size dernières phrases)
        # Note: Dans une vraie approche live avec "vision du futur", on détecterait le début 
        # de la chronique à (total - window_size + 1)
        current_context = " ".join(self.sentence_buffer[-self.window_size:])
        
        inputs = self.tokenizer(
            current_context, 
            return_tensors="pt", 
            truncation=True, 
            max_length=256
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            prob_start = probs[0][1].item()
            
        detection = None
        if prob_start >= self.threshold:
            # Vérification du gap pour éviter les rafales
            # On considère que le début est la PREMIÈRE phrase du buffer actuel
            detection_idx = self.total_sentences_processed - self.window_size + 1
            
            if detection_idx > self.last_detection_index + self.min_gap:
                self.last_detection_index = detection_idx
                detection = {
                    "index": detection_idx,
                    "confidence": prob_start,
                    "trigger_sentence": self.sentence_buffer[-self.window_size],
                    "context": current_context
                }
        
        # On garde le buffer à la taille de la fenêtre pour économiser la mémoire
        if len(self.sentence_buffer) > self.window_size:
            self.sentence_buffer.pop(0)
            
        return detection

def simulate_live_stream(file_path, detector, delay=0.5):
    """
    Simule la lecture d'un fichier comme un flux de phrases.
    """
    if not os.path.exists(file_path):
        print(f"Erreur: {file_path} introuvable")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Nettoyage si SRT
    if file_path.endswith(".srt"):
        from inference import clean_srt_content
        content = clean_srt_content(content)

    # Découpage initial pour la simulation (en réalité, les phrases arriveraient une par une)
    text = content.replace('\n', ' ').strip()
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 5]

    print(f"Début de la simulation live sur {len(sentences)} phrases...")
    print("-" * 50)

    for i, s in enumerate(sentences):
        # Simulation du délai de réception/transcription
        time.sleep(delay)
        
        # Affichage discret de la progression
        print(f"\r[Flux] Reçu: {s[:60]}...", end="", flush=True)
        
        result = detector.process_new_sentence(s)
        
        if result:
            print(f"\n\n{'='*20} CHRONIQUE DÉTECTÉE {'='*20}")
            print(f"Phrase n°: {result['index']}")
            print(f"Confiance: {result['confidence']:.4f}")
            print(f"Contenu: {result['trigger_sentence']}")
            print(f"{'='*60}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulation d'inférence en flux live.")
    parser.add_argument("file", help="Fichier de transcription")
    parser.add_argument("--model", default="./camembert_chronicle_start_v2")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--delay", type=float, default=0.2, help="Délai entre chaque phrase (secondes)")
    
    args = parser.parse_args()
    
    detector = LiveChronicleDetector(
        model_path=args.model, 
        window_size=args.window, 
        threshold=args.threshold
    )
    
    try:
        simulate_live_stream(args.file, detector, delay=args.delay)
    except KeyboardInterrupt:
        print("\nSimulation arrêtée.")
