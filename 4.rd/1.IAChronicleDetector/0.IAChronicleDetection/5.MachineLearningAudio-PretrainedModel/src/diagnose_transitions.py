import os
import json
import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor

SAMPLING_RATE = 16000
AUDIO_PATH = "10075-07.04.2026-ITEMA_24467552-2026C6608S0097-NET_MFC_BE8424AB-0782-4064-B140-DD0480F89F2A-21-0097c3eba2e7ff163fc0dd719431af92.mp3"
MODEL_DIR = "./model_output_ast"

TARGET_TIMECODES = [
    ("00:03", "07:55"), ("08:00", "14:22"), ("14:22", "15:30"), ("15:38", "21:15"),
    ("22:32", "27:27"), ("27:31", "30:18"), ("30:32", "43:18"), ("43:20", "47:48"),
    ("48:21", "1:00:02"), ("1:00:36", "1:06:39"), ("1:06:46", "1:13:06"),
    ("1:13:23", "1:30:39"), ("1:30:41", "1:45:54"), ("1:47:26", "1:51:21"),
    ("1:51:30", "2:13:56"), ("2:15:33", "2:23:00"), ("2:23:06", "2:26:18"), ("2:26:18", "2:30:00")
]

def time_to_seconds(t_str: str) -> float:
    parts = list(map(int, t_str.split(':')))
    if len(parts) == 2: return parts[0] * 60 + parts[1]
    elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0.0

TARGET_SECONDS = [(time_to_seconds(s), time_to_seconds(e)) for s, e in TARGET_TIMECODES]

def main():
    print(f"Loading AST model from {MODEL_DIR}...")
    model = ASTForAudioClassification.from_pretrained(MODEL_DIR)
    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_DIR)
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device)
    model.eval()

    print(f"Loading audio...")
    audio, sr = librosa.load(AUDIO_PATH, sr=SAMPLING_RATE)
    
    window_size = 10.0
    overlap = 9.0 # Very high overlap for high resolution (1s step)
    step = window_size - overlap
    
    # We only analyze points of interest (transitions)
    transitions = []
    for s, e in TARGET_SECONDS:
        transitions.append(s)
        transitions.append(e)
    
    results = {}
    
    print("Analyzing transitions...")
    for t in sorted(list(set(transitions))):
        start_scan = max(0, t - 15)
        end_scan = min(len(audio)/SAMPLING_RATE, t + 15)
        
        confs = []
        for start in np.arange(start_scan, end_scan - window_size, 1.0):
            segment = audio[int(start * SAMPLING_RATE):int((start + window_size) * SAMPLING_RATE)]
            inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                     max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = model(**inputs).logits
                probs = torch.softmax(logits, dim=-1)
            
            conf = probs[0][1].item() # Confidence for 'chronique'
            confs.append((start, conf))
        
        results[t] = confs
        
    # Find a global threshold that works for most transitions
    # A transition is successful if confidence is HIGH inside target and LOW outside
    # Let's just print the confidences around target times to see the "gap"
    for t_idx, (t_start, t_end) in enumerate(TARGET_SECONDS):
        print(f"\nTarget {t_idx+1}: {t_start}s - {t_end}s")
        # Conf around start
        c_start = [c for s, c in results[t_start] if abs(s - t_start) < 2]
        c_end = [c for s, c in results[t_end] if abs(s - t_end) < 2]
        print(f"  Conf at Start: {np.mean(c_start) if c_start else 'N/A'}")
        print(f"  Conf at End:   {np.mean(c_end) if c_end else 'N/A'}")

if __name__ == "__main__":
    main()
