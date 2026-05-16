import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor
import argparse
import json

SAMPLING_RATE = 16000

def analyze_probs(audio_path, model_dir, window_size=10.0, overlap=5.0):
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")
    
    model = ASTForAudioClassification.from_pretrained(model_dir)
    feature_extractor = ASTFeatureExtractor.from_pretrained(model_dir)
    model.to(device)
    model.eval()

    audio, sr = librosa.load(audio_path, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    step = window_size - overlap
    
    results = []
    
    for start in np.arange(0, duration, step):
        end = min(start + window_size, duration)
        if end - start < 2.0:
            continue
            
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                 max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            
        results.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "probs": probs[0].tolist(),
            "pred_id": torch.argmax(probs, dim=-1).item()
        })
        
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=str)
    parser.add_argument("--model_dir", type=str, default="./model_output_ast")
    args = parser.parse_args()
    
    analysis = analyze_probs(args.audio, args.model_dir)
    
    # Just print the first 20 segments to see what's happening
    print("First 20 segments analysis:")
    for r in analysis[:20]:
        print(f"Time: {r['start']:.2f}-{r['end']:.2f} | Probs: {r['probs']} | Pred: {r['pred_id']}")
    
    # Check if there are ANY background predictions
    background_count = sum(1 for r in analysis if r['pred_id'] == 0)
    chronique_count = sum(1 for r in analysis if r['pred_id'] == 1)
    print(f"\nTotal segments: {len(analysis)}")
    print(f"Background segments: {background_count}")
    print(f"Chronique segments: {chronique_count}")
