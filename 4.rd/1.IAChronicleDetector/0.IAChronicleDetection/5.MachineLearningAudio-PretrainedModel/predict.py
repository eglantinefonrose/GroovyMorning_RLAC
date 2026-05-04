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

def predict(audio_path: str, window_size: float = 10.0, overlap: float = 5.0, threshold: float = 0.1):
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
        if end - start < 2.0: # Skip very short segments at the end
            continue
            
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            
        confidence, pred_id = torch.max(probs, dim=-1)
        confidence = confidence.item()
        pred_id = pred_id.item()
        label = model.config.id2label[pred_id]
        
        # Skip background or low confidence
        if label == "background" or confidence < threshold:
            continue
        
        predictions.append({
            "label": label,
            "start": start,
            "end": end,
            "confidence": confidence
        })

    # Merge consecutive segments with same label
    if not predictions:
        return []

    merged = []
    if predictions:
        current = predictions[0].copy()
        
        for i in range(1, len(predictions)):
            next_seg = predictions[i]
            # Merge if same label AND they are close enough in time
            if next_seg["label"] == current["label"] and next_seg["start"] <= current["end"] + step:
                current["end"] = next_seg["end"]
                # Keep max confidence or average? Let's keep max for now
                current["confidence"] = max(current["confidence"], next_seg["confidence"])
            else:
                merged.append(current)
                current = next_seg.copy()
        merged.append(current)
    
    # Filter out very short chronicles (e.g. < 15s) that might be false positives
    merged = [m for m in merged if (m["end"] - m["start"]) >= 5.0]
    
    # Format output
    result = []
    for m in merged:
        result.append({
            "chronique": m["label"],
            "start": format_time(m["start"]),
            "end": format_time(m["end"]),
            "confidence": round(m["confidence"], 3)
        })
        
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict chronicles in an audio file.")
    parser.add_argument("audio", type=str, help="Path to audio file (mp3 or m4a)")
    parser.add_argument("--window", type=float, default=10.0, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=5.0, help="Overlap in seconds")
    parser.add_argument("--threshold", type=float, default=0.4, help="Confidence threshold (0-1)")
    parser.add_argument("--output", type=str, help="Path to save JSON output")
    
    args = parser.parse_args()
    
    results = predict(args.audio, args.window, args.overlap, args.threshold)
    
    print("\nDetected Chronicles:")
    print(json.dumps(results, indent=4, ensure_ascii=False))
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")
