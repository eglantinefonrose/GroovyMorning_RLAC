import os
import argparse
import json
import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor
from typing import List, Dict
import sys

# Import local ModelLoader to handle checkpoints correctly
from models_loader import ModelLoader

SAMPLING_RATE = 16000

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

class JingleHybridDetector:
    def __init__(self, jingle_model_path="./model_output_jingle", chronicle_model_path="./model_output_ast"):
        self.loader = ModelLoader()
        self.device = self.loader.device
        print(f"Using device: {self.device}")
        
        # We use the loader's _get_effective_path to find the latest checkpoint if needed
        self.jingle_path = self.loader._get_effective_path(jingle_model_path)
        print(f"Loading Jingle model from {self.jingle_path}...")
        self.jingle_extractor = ASTFeatureExtractor.from_pretrained(self.jingle_path)
        self.jingle_model = ASTForAudioClassification.from_pretrained(self.jingle_path).to(self.device)
        self.jingle_model.eval()
        
        self.chronicle_path = self.loader._get_effective_path(chronicle_model_path)
        print(f"Loading Chronicle model from {self.chronicle_path}...")
        self.chronicle_extractor = ASTFeatureExtractor.from_pretrained(self.chronicle_path)
        self.chronicle_model = ASTForAudioClassification.from_pretrained(self.chronicle_path).to(self.device)
        self.chronicle_model.eval()

    def get_prob(self, segment, model, extractor, window_size):
        if len(segment) < 1600: # Less than 0.1s is too short
            return 0.0
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
        
        jingle_window = 1.0
        chronicle_window = 1.0
        step = 1.0 # 1s step for jingle precision
        
        results = []
        
        print("\n" + "="*50)
        print("  STARTING DETAILED HYBRID DETECTION")
        print("="*50 + "\n")
        
        current_time = 0
        while current_time < duration - chronicle_window:
            # 1. Look for a Jingle
            jingle_segment = audio[int(current_time * SAMPLING_RATE):int((current_time + jingle_window) * SAMPLING_RATE)]
            j_prob = self.get_prob(jingle_segment, self.jingle_model, self.jingle_extractor, jingle_window)
            
            if j_prob >= jingle_threshold:
                print(f"\n[🔔 JINGLE] Detected at {format_time(current_time)} (Conf: {j_prob:.4f})")
                
                start_time = current_time
                # 2. Follow the chronicle until it ends
                end_time = current_time + chronicle_window
                
                consecutive_low_conf = 0
                temp_time = current_time
                
                print(f"  Tracking chronicle content:")
                
                while temp_time < duration - chronicle_window:
                    chr_segment = audio[int(temp_time * SAMPLING_RATE):int((temp_time + chronicle_window) * SAMPLING_RATE)]
                    c_prob = self.get_prob(chr_segment, self.chronicle_model, self.chronicle_extractor, chronicle_window)
                    
                    is_chronicle = c_prob >= chronicle_threshold
                    status = "✅ CHRONICLE " if is_chronicle else "❌ BACKGROUND"
                    print(f"    - [{format_time(temp_time)} - {format_time(temp_time + chronicle_window)}] {status} (Conf: {c_prob:.4f})")
                    
                    if not is_chronicle:
                        consecutive_low_conf += 1
                    else:
                        consecutive_low_conf = 0
                        end_time = temp_time + chronicle_window
                    
                    # If we have 15s of non-chronique, we stop (15 segments of 1s)
                    if consecutive_low_conf >= 15:
                        print(f"  [STOP] End of chronicle detected (15s of low confidence reached).")
                        break
                    
                    temp_time += 1.0 # Scan by 1s jumps
                
                duration_detected = end_time - start_time
                if duration_detected >= min_duration:
                    results.append({
                        "start_time": format_time(start_time),
                        "end_time": format_time(end_time),
                        "start_sec": start_time,
                        "end_sec": end_time,
                        "jingle_confidence": j_prob,
                        "duration": duration_detected
                    })
                    print(f"\n[✨ RESULT] Chronicle saved: {format_time(start_time)} -> {format_time(end_time)} ({duration_detected:.1f}s)")
                else:
                    print(f"\n[⚠️ REJECTED] Segment too short ({duration_detected:.1f}s < {min_duration}s)")
                    
                # Skip forward after the detected chronicle
                current_time = end_time
                print("\n" + "-"*30 + " Resuming Jingle Scan " + "-"*30)
            else:
                current_time += step
                
            # Periodic progress update (every 5 minutes of audio)
            if int(current_time) % 300 == 0 and int(current_time) > 0 and (current_time - step) < int(current_time):
                print(f"Progress: {current_time/duration*100:.1f}% ({format_time(current_time)} / {format_time(duration)})")
                
        return results

def main():
    parser = argparse.ArgumentParser(description="Detailed Hybrid Jingle-based Chronicle Detection")
    parser.add_argument("audio", type=str, help="Path to the audio file")
    parser.add_argument("--jingle_threshold", type=float, default=0.8, help="Threshold for jingle detection (default: 0.8)")
    parser.add_argument("--chronicle_threshold", type=float, default=0.5, help="Threshold for chronicle maintenance (default: 0.5)")
    parser.add_argument("--min_duration", type=float, default=10.0, help="Minimum duration for a chronicle in seconds (default: 10.0)")
    parser.add_argument("--output", type=str, default="resultat_jingle_hybride.json", help="Output JSON file (default: resultat_jingle_hybride.json)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found: {args.audio}")
        sys.exit(1)
        
    detector = JingleHybridDetector()
    detections = detector.detect(
        args.audio, 
        jingle_threshold=args.jingle_threshold, 
        chronicle_threshold=args.chronicle_threshold,
        min_duration=args.min_duration
    )
    
    print("\n" + "="*50)
    print(f"  DETECTION SUMMARY: {len(detections)} Chronicles Found")
    print("="*50)
    for i, d in enumerate(detections):
        print(f"{i+1}. {d['start_time']} - {d['end_time']} (Dur: {d['duration']:.1f}s, Jingle Conf: {d['jingle_confidence']:.2f})")
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(detections, f, indent=4, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
