import os
import argparse
import json
import torch
import librosa
import numpy as np
from pydub import AudioSegment
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor
from typing import List, Dict

SAMPLING_RATE = 16000
MODEL_DIR = "./model_output"

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def predict(audio_path: str, window_size: float = 10.0, overlap: float = 5.0):
    # Load model and feature extractor
    print(f"Loading model from {MODEL_DIR}...")
    model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_DIR)
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    # Load audio
    print(f"Loading audio {audio_path}...")
    audio, sr = librosa.load(audio_path, sr=SAMPLING_RATE)
    
    duration = len(audio) / SAMPLING_RATE
    step = window_size - overlap
    
    predictions = []
    
    print("Running sliding window inference...")
    for start in np.arange(0, duration, step):
        end = min(start + window_size, duration)
        if end - start < 1.0: # Skip very short segments at the end
            continue
            
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            
        pred_id = torch.argmax(logits, dim=-1).item()
        label = model.config.id2label[pred_id]
        
        predictions.append({
            "label": label,
            "start": start,
            "end": end
        })

    # Merge consecutive segments
    if not predictions:
        return []

    merged = []
    current = predictions[0].copy()
    
    for i in range(1, len(predictions)):
        next_seg = predictions[i]
        if next_seg["label"] == current["label"]:
            current["end"] = next_seg["end"]
        else:
            merged.append(current)
            current = next_seg.copy()
    merged.append(current)
    
    # Format output
    result = []
    for m in merged:
        result.append({
            "chronique": m["label"],
            "start": format_time(m["start"]),
            "end": format_time(m["end"])
        })
        
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict chronicles in an audio file.")
    parser.add_argument("audio", type=str, help="Path to audio file (mp3 or m4a)")
    parser.add_argument("--window", type=float, default=10.0, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=5.0, help="Overlap in seconds")
    parser.add_argument("--output", type=str, help="Path to save JSON output")
    
    args = parser.parse_args()
    
    results = predict(args.audio, args.window, args.overlap)
    
    print("\nDetected Chronicles:")
    print(json.dumps(results, indent=4, ensure_ascii=False))
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")
