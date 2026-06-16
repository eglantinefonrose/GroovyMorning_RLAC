import os
import argparse
import json
import torch
import librosa
import numpy as np
from transformers import (
    AutoModelForAudioClassification, 
    AutoFeatureExtractor,
    ASTForAudioClassification,
    ASTFeatureExtractor,
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    WavLMForSequenceClassification
)
from typing import List, Dict

SAMPLING_RATE = 16000

MODEL_CONFIGS = {
    "wav2vec2": {
        "dir": "./model_output",
        "model_class": Wav2Vec2ForSequenceClassification,
        "extractor_class": Wav2Vec2FeatureExtractor
    },
    "ast": {
        "dir": "./model_output_ast",
        "model_class": ASTForAudioClassification,
        "extractor_class": ASTFeatureExtractor
    },
    "beats": {
        "dir": "./model_output_beats",
        "model_class": AutoModelForAudioClassification,
        "extractor_class": AutoFeatureExtractor
    },
    "wavlm": {
        "dir": "./model_output_wavlm",
        "model_class": WavLMForSequenceClassification,
        "extractor_class": Wav2Vec2FeatureExtractor
    }
}

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def predict_robust(audio_path: str, model_type: str, model_dir: str = None,
                  window_size: float = 10.0, overlap: float = 8.0, 
                  threshold_start: float = 0.7, threshold_end: float = 0.3,
                  smooth_window: int = 3, min_duration: float = 10.0, debug: bool = False):
    
    config = MODEL_CONFIGS.get(model_type, MODEL_CONFIGS["ast"])
    if not model_dir:
        model_dir = config["dir"]
        
    print(f"Loading {model_type} model from {model_dir}...")
    model = config["model_class"].from_pretrained(model_dir)
    feature_extractor = config["extractor_class"].from_pretrained(model_dir)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device)
    model.eval()

    print(f"Loading audio {audio_path}...")
    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    step = window_size - overlap
    
    # 1. Collect raw probabilities for all windows
    raw_probs = []
    timestamps = []
    
    print("Inference running...")
    for start in np.arange(0, duration - 2.0, step):
        end = min(start + window_size, duration)
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        if model_type == "ast":
             inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                     max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        else:
             inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt")
        
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        
        # probs[0] contains [prob_background, prob_chronique]
        p_bg = probs[0][0].item()
        p_ch = probs[0][1].item()
        
        # We store the "diff" or a weighted score
        # If p_ch is not clearly > p_bg, we penalize it
        score = p_ch if p_ch > p_bg else p_ch * 0.5
        raw_probs.append(score)
        timestamps.append(start)

    # 2. Smooth probabilities
    smoothed_probs = np.convolve(raw_probs, np.ones(smooth_window)/smooth_window, mode='same')

    # 3. Hysteresis Thresholding with Gap Detection
    detected_segments = []
    is_active = False
    current_start = 0
    current_max_conf = 0
    
    for i in range(len(smoothed_probs)):
        prob = smoothed_probs[i]
        time = timestamps[i]
        
        if not is_active:
            if prob >= threshold_start:
                is_active = True
                current_start = time
                current_max_conf = prob
        else:
            current_max_conf = max(current_max_conf, prob)
            # Conditions to end a segment:
            # - Probability drops below threshold_end
            # - Or we reached the end of the file
            if prob < threshold_end or i == len(smoothed_probs) - 1:
                is_active = False
                # The end is the end of the last window that was still "active"
                current_end = time + (window_size / 2) # Approximate end
                
                if (current_end - current_start) >= min_duration:
                    detected_segments.append({
                        "label": "chronique",
                        "chronique": "chronique",
                        "start": format_time(current_start),
                        "end": format_time(current_end),
                        "confidence": round(current_max_conf, 3)
                    })

    if debug:
        for i in range(len(raw_probs)):
             print(f"Time: {format_time(timestamps[i])} | Score: {raw_probs[i]:.3f} | Smoothed: {smoothed_probs[i]:.3f}")

    return detected_segments

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Robust prediction for chronicles.")
    parser.add_argument("audio", type=str)
    parser.add_argument("--model_type", type=str, default="ast")
    parser.add_argument("--model_dir", type=str)
    parser.add_argument("--threshold_start", type=float, default=0.7)
    parser.add_argument("--threshold_end", type=float, default=0.3)
    parser.add_argument("--window", type=float, default=10.0)
    parser.add_argument("--overlap", type=float, default=8.0)
    parser.add_argument("--smooth_window", type=int, default=3)
    parser.add_argument("--min_duration", type=float, default=10.0)
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    results = predict_robust(
        audio_path=args.audio,
        model_type=args.model_type,
        model_dir=args.model_dir,
        window_size=args.window,
        overlap=args.overlap,
        threshold_start=args.threshold_start,
        threshold_end=args.threshold_end,
        smooth_window=args.smooth_window,
        min_duration=args.min_duration,
        debug=args.debug
    )
    
    print(f"\nTotal Chronicles Detected: {len(results)}")
    print(json.dumps(results, indent=4, ensure_ascii=False))
