import argparse
import json
import sys
import os
from pathlib import Path
import torch
from faster_whisper import WhisperModel
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from tqdm import tqdm

def transcribe_audio(audio_path, model_size="base"):
    """Transcrire l'audio en segments compatibles avec le classifier"""
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

def predict_chroniques(model_path, segments, threshold=0.5):
    """Prédit les chroniques avec le modèle Transformer"""
    if not segments:
        return []

    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    model.eval()
    
    device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
    model.to(device)

    # Préparation des textes avec contexte
    texts = []
    window_size = 2
    for i in range(len(segments)):
        start_idx = max(0, i - window_size)
        end_idx = min(len(segments), i + window_size + 1)
        context_texts = [segments[j]['text'] for j in range(start_idx, end_idx)]
        texts.append(" [SEP] ".join(context_texts))
    
    batch_size = 16
    all_probs = []
    
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            encodings = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt"
            ).to(device)
            
            outputs = model(**encodings)
            probs = torch.softmax(outputs.logits, dim=1)[:, 1].cpu().tolist()
            all_probs.extend(probs)

    detected_chroniques = []
    current_start = None
    current_end = None
    max_conf = 0
    
    for i, prob in enumerate(all_probs):
        if prob >= threshold:
            if current_start is None:
                current_start = segments[i]['start']
            current_end = segments[i]['end']
            max_conf = max(max_conf, prob)
        else:
            if current_start is not None:
                if current_end - current_start >= 5.0:
                    detected_chroniques.append({
                        "start": round(current_start, 2),
                        "end": round(current_end, 2),
                        "label": "chronique",
                        "confidence": round(float(max_conf), 3)
                    })
                current_start = None
                max_conf = 0
                
    if current_start is not None:
        if current_end - current_start >= 5.0:
            detected_chroniques.append({
                "start": round(current_start, 2),
                "end": round(current_end, 2),
                "label": "chronique",
                "confidence": round(float(max_conf), 3)
            })
            
    return detected_chroniques

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche Transformer)")
    parser.add_argument("audio", help="Chemin vers le fichier audio")
    parser.add_argument("--model", default="models/camembert_chronicle", help="Modèle Transformer")
    parser.add_argument("--threshold", type=float, default=0.5, help="Seuil de confiance")
    parser.add_argument("--whisper-model", default="base", help="Taille du modèle Whisper")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        print(f"Erreur: Fichier audio non trouvé: {args.audio}", file=sys.stderr)
        sys.exit(1)
        
    segments = transcribe_audio(args.audio, model_size=args.whisper_model)
    results = predict_chroniques(args.model, segments, threshold=args.threshold)
    
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
