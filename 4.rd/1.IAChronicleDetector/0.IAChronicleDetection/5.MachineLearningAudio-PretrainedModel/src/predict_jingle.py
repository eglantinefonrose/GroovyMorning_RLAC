import os
import argparse
import json
import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor

SAMPLING_RATE = 16000

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def predict_jingles(audio_path, model_path="./model_output_jingle", threshold=0.8, window_size=5.0, step=1.0):
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")
    
    print(f"Loading Jingle model from {model_path}...")
    extractor = ASTFeatureExtractor.from_pretrained(model_path)
    model = ASTForAudioClassification.from_pretrained(model_path).to(device)
    model.eval()

    print(f"Loading audio {audio_path}...")
    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    
    jingle_detections = []
    
    print(f"Scanning for jingles (threshold={threshold})...")
    
    for start in np.arange(0, duration - window_size, step):
        end = start + window_size
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        inputs = extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                          max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            
        prob = probs[0][1].item()
        
        if prob >= threshold:
            jingle_detections.append({
                "time": start,
                "confidence": prob
            })
            
    if not jingle_detections:
        return []

    # Merge consecutive windows into discrete jingle events
    merged_jingles = []
    if jingle_detections:
        current_jingle = {
            "start": jingle_detections[0]["time"],
            "end": jingle_detections[0]["time"] + window_size,
            "max_conf": jingle_detections[0]["confidence"]
        }
        
        for i in range(1, len(jingle_detections)):
            d = jingle_detections[i]
            # If detection is within 3 seconds of the current one, merge it
            if d["time"] <= current_jingle["end"] + 2.0:
                current_jingle["end"] = d["time"] + window_size
                current_jingle["max_conf"] = max(current_jingle["max_conf"], d["confidence"])
            else:
                merged_jingles.append(current_jingle)
                current_jingle = {
                    "start": d["time"],
                    "end": d["time"] + window_size,
                    "max_conf": d["confidence"]
                }
        merged_jingles.append(current_jingle)
        
    return merged_jingles

def main():
    parser = argparse.ArgumentParser(description="Detect only jingles in an audio file")
    parser.add_argument("audio", type=str, help="Path to audio file")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold")
    parser.add_argument("--model", type=str, default="./model_output_jingle", help="Path to jingle model")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.model):
        print(f"Error: Jingle model not found at {args.model}")
        print("Please train the model first using: python src/train/train_jingle.py")
        return

    jingles = predict_jingles(args.audio, model_path=args.model, threshold=args.threshold)
    
    print("\n" + "="*40)
    print(f"JINGLES DÉTECTÉS ({len(jingles)}) :")
    print("="*40)
    
    for i, j in enumerate(jingles):
        print(f"Jingle #{i+1:02d} : {format_time(j['start'])} (Conf: {j['max_conf']:.3f})")
    
    print("="*40)

if __name__ == "__main__":
    main()
