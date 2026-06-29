import os
import argparse
import json
import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor
from typing import List, Dict
import sys

SAMPLING_RATE = 16000

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

class HybridDetector:
    def __init__(self, jingle_model_path="./model_output_jingle", chronicle_model_path="./model_output_ast"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        print(f"Loading Jingle model from {jingle_model_path}...")
        self.jingle_extractor = ASTFeatureExtractor.from_pretrained(jingle_model_path)
        self.jingle_model = ASTForAudioClassification.from_pretrained(jingle_model_path).to(self.device)
        self.jingle_model.eval()
        
        print(f"Loading Chronicle model from {chronicle_model_path}...")
        self.chronicle_extractor = ASTFeatureExtractor.from_pretrained(chronicle_model_path)
        self.chronicle_model = ASTForAudioClassification.from_pretrained(chronicle_model_path).to(self.device)
        self.chronicle_model.eval()

    def get_prob(self, segment, model, extractor, window_size):
        inputs = extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                          max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        return probs[0][1].item()

    def detect(self, audio_path, jingle_threshold=0.8, chronicle_threshold=0.5, min_duration=10.0):
        print(f"Processing audio: {audio_path}")
        audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
        duration = len(audio) / SAMPLING_RATE
        
        jingle_window = 0.5
        chronicle_window = 1.0
        step = 1.0 # 1s step for precision
        
        results = []
        
        print("Starting Hybrid Detection (Jingle Landmarks)...")
        
        current_time = 0
        while current_time < duration - chronicle_window:
            # 1. Look for a Jingle
            jingle_segment = audio[int(current_time * SAMPLING_RATE):int((current_time + jingle_window) * SAMPLING_RATE)]
            j_prob = self.get_prob(jingle_segment, self.jingle_model, self.jingle_extractor, jingle_window)
            
            if j_prob >= jingle_threshold:
                print(f"Found Jingle at {format_time(current_time)} (Prob: {j_prob:.3f})")
                
                start_time = current_time
                # 2. Follow the chronicle until it ends
                # We use a larger window and step to find the end
                end_time = current_time + chronicle_window
                
                # Check chronicle presence
                consecutive_low_conf = 0
                temp_time = current_time
                
                while temp_time < duration - chronicle_window:
                    chr_segment = audio[int(temp_time * SAMPLING_RATE):int((temp_time + chronicle_window) * SAMPLING_RATE)]
                    c_prob = self.get_prob(chr_segment, self.chronicle_model, self.chronicle_extractor, chronicle_window)
                    
                    if c_prob < chronicle_threshold:
                        consecutive_low_conf += 1
                    else:
                        consecutive_low_conf = 0
                        end_time = temp_time + chronicle_window
                    
                    # If we have 15s of non-chronique, we stop
                    if consecutive_low_conf >= 15:
                        break
                    
                    temp_time += 5.0 # Faster scan for the end
                
                if (end_time - start_time) >= min_duration:
                    results.append({
                        "start_time": format_time(start_time),
                        "end_time": format_time(end_time),
                        "start_sec": start_time,
                        "end_sec": end_time,
                        "jingle_confidence": j_prob
                    })
                    print(f"  Chronicle detected: {format_time(start_time)} - {format_time(end_time)}")
                    
                # Skip forward
                current_time = end_time
            else:
                current_time += step
                
            if int(current_time) % 500 == 0:
                print(f"Progress: {current_time/duration*100:.1f}%")
                
        return results

def main():
    parser = argparse.ArgumentParser(description="Hybrid Jingle-based Chronicle Detection")
    parser.add_argument("audio", type=str)
    parser.add_argument("--jingle_threshold", type=float, default=0.8)
    parser.add_argument("--chronicle_threshold", type=float, default=0.5)
    parser.add_argument("--output", type=str, default="resultat_hybride.json")
    
    args = parser.parse_args()
    
    detector = HybridDetector()
    detections = detector.detect(args.audio, jingle_threshold=args.jingle_threshold, chronicle_threshold=args.chronicle_threshold)
    
    print(f"\nDetected {len(detections)} chronicles:")
    for d in detections:
        print(f"  {d['start_time']} - {d['end_time']} (Jingle Conf: {d['jingle_confidence']:.2f})")
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(detections, f, indent=4, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
