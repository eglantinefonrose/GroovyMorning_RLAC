import argparse
import json
import sys
import os
import torch
from faster_whisper import WhisperModel
from transformers import CamembertTokenizer, CamembertForSequenceClassification

def transcribe_audio(audio_path, model_size="base"):
    """Transcrire l'audio en segments avec timestamps"""
    print(f"Transcription de {audio_path} avec Whisper ({model_size})...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, language="fr")
    
    formatted_segments = []
    for segment in segments:
        formatted_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip()
        })
    return formatted_segments

def predict_starts(model_path, segments, threshold=0.85):
    """Détecte les débuts de chroniques dans les segments transcrits"""
    print(f"Chargement du modèle depuis {model_path}...", file=sys.stderr)
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    detected_chroniques = []
    
    for seg in segments:
        text = seg['text']
        if len(text) < 10: continue
        
        inputs = tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=128
        ).to(device)
        
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            prob_start = probs[0][1].item()
            
            if prob_start >= threshold:
                detected_chroniques.append({
                    "start": round(seg['start'], 2),
                    "end": round(seg['start'] + 60.0, 2), # Durée arbitraire d'une minute par défaut car on ne détecte que le début ici
                    "label": "début de chronique",
                    "sentence": text,
                    "confidence": round(prob_start, 3)
                })
    
    return detected_chroniques

def main():
    parser = argparse.ArgumentParser(description="Détecte les débuts de chroniques (Approche CamemBERT Start)")
    parser.add_argument("audio", help="Chemin vers le fichier audio")
    parser.add_argument("--model", default="./camembert_chronicle_start_v4", help="Modèle CamemBERT")
    parser.add_argument("--threshold", type=float, default=0.85, help="Seuil de confiance")
    parser.add_argument("--whisper-model", default="base", help="Taille du modèle Whisper")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)
        
    segments = transcribe_audio(args.audio, model_size=args.whisper_model)
    results = predict_starts(args.model, segments, threshold=args.threshold)
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
