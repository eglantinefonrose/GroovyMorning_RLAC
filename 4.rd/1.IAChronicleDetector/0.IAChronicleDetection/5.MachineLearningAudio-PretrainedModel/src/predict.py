import os
import argparse
import json
import torch
import librosa
import numpy as np
from pydub import AudioSegment
from transformers import (
    AutoModelForAudioClassification, 
    AutoFeatureExtractor,
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    ASTForAudioClassification,
    ASTFeatureExtractor,
    WavLMForSequenceClassification
)
from typing import List, Dict

SAMPLING_RATE = 16000

# Mapping of model types to their default directories and classes
MODEL_CONFIGS = {
    "wav2vec2": {
        "dir": "./model_output",
        "binary_dir": "./model_output_binary",
        "model_class": Wav2Vec2ForSequenceClassification,
        "extractor_class": Wav2Vec2FeatureExtractor
    },
    "ast": {
        "dir": "./model_output_ast",
        "binary_dir": "./model_output_ast",
        "model_class": ASTForAudioClassification,
        "extractor_class": ASTFeatureExtractor
    },
    "beats": {
        "dir": "./model_output_beats",
        "binary_dir": "./model_output_beats",
        "model_class": AutoModelForAudioClassification,
        "extractor_class": AutoFeatureExtractor
    },
    "wavlm": {
        "dir": "./model_output_wavlm",
        "binary_dir": "./model_output_wavlm",
        "model_class": WavLMForSequenceClassification,
        "extractor_class": Wav2Vec2FeatureExtractor
    },
    "cnn": {
        "dir": "./model_output_cnn",
        "binary_dir": "./model_output_cnn",
        "model_class": AutoModelForAudioClassification,
        "extractor_class": AutoFeatureExtractor
    }
}

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

import time

def predict(audio_path: str, model_type: str, model_dir: str = None, is_binary: bool = False, 
            window_size: float = 10.0, overlap: float = 5.0, threshold: float = 0.4, 
            gap_filling: float = 5.0, min_duration: float = 5.0, debug: bool = False,
            acceleration: float = 0.0):
    
    config = MODEL_CONFIGS.get(model_type, MODEL_CONFIGS["wav2vec2"])
    
    if not model_dir:
        model_dir = config["binary_dir"] if is_binary else config["dir"]
        
    print(f"Loading {model_type} model from {model_dir}...")
    
    model_class = config["model_class"]
    extractor_class = config["extractor_class"]
    
    model = model_class.from_pretrained(model_dir)
    feature_extractor = extractor_class.from_pretrained(model_dir)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")
    model.to(device)
    model.eval()

    # Load audio
    print(f"Loading audio {audio_path}...")
    audio, sr = librosa.load(audio_path, sr=SAMPLING_RATE)
    
    duration = len(audio) / SAMPLING_RATE
    step = window_size - overlap
    
    predictions = []
    
    print("Running sliding window inference...")
    
    # Pre-check feature extractor padding/max_length requirements
    is_ast = (model_type == "ast")
    
    t0 = time.time()
    for start in np.arange(0, duration, step):
        if acceleration > 0:
            target_time = start / acceleration
            elapsed = time.time() - t0
            sleep_time = target_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        end = min(start + window_size, duration)
        if end - start < 2.0: # Skip very short segments
            continue
            
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        
        # AST requires specific padding to max_length
        if is_ast:
            inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                     max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        else:
            inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", padding=True)
            
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            
        # We store the probability of 'chronique' (label 1)
        chronique_prob = probs[0][1].item()
        
        # Determine pred_id for internal reference
        pred_id = torch.argmax(probs, dim=-1).item()
        
        predictions.append({
            "start": start,
            "end": end,
            "prob": chronique_prob,
            "pred_id": pred_id
        })

    if not predictions:
        return []

    for i, p in enumerate(predictions):
        # Re-evaluate label based on raw prob and threshold
        label = "chronique" if p["prob"] >= threshold else "background"
        p["label"] = label
        p["confidence"] = p["prob"]

    # Filter out background segments for merging
    active_segments = [p for p in predictions if p["label"] == "chronique"]
    
    if not active_segments:
        return []

    # Merge consecutive segments with same label
    merged = []
    current = active_segments[0].copy()
    
    for i in range(1, len(active_segments)):
        next_seg = active_segments[i]
        # Merge if they are close enough in time (Gap Filling)
        if next_seg["start"] <= current["end"] + gap_filling + 0.1: # 0.1 for float safety
            current["end"] = next_seg["end"]
            current["confidence"] = max(current["confidence"], next_seg["confidence"])
        else:
            merged.append(current)
            current = next_seg.copy()
    merged.append(current)
    
    # Filter out very short chronicles
    merged = [m for m in merged if (m["end"] - m["start"]) >= min_duration]
    
    result = []
    for m in merged:
        result.append({
            "label": m["label"],
            "chronique": m["label"],
            "start": format_time(m["start"]),
            "end": format_time(m["end"]),
            "confidence": round(m["confidence"], 3)
        })
        
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict chronicles in an audio file.")
    parser.add_argument("audio", type=str, help="Path to audio file")
    parser.add_argument("--model_type", type=str, default="wav2vec2", choices=["wav2vec2", "ast", "beats", "wavlm", "cnn"], help="Type of model to use")
    parser.add_argument("--window", type=float, default=10.0, help="Window size in seconds")
    parser.add_argument("--overlap", type=float, default=5.0, help="Overlap in seconds")
    parser.add_argument("--threshold", type=float, default=0.4, help="Confidence threshold")
    parser.add_argument("--gap_filling", type=float, default=5.0, help="Max gap (seconds) to fill between segments of same label")
    parser.add_argument("--min_duration", type=float, default=5.0, help="Minimum duration (seconds) for a detected chronicle")
    parser.add_argument("--debug", action="store_true", help="Show raw predictions per window")
    parser.add_argument("--binary", action="store_true", help="Use binary model version")
    parser.add_argument("--model_dir", type=str, help="Custom model directory")
    parser.add_argument("--output", type=str, help="Path to save JSON output")
    
    args = parser.parse_args()
    
    results = predict(
        audio_path=args.audio,
        model_type=args.model_type,
        model_dir=args.model_dir,
        is_binary=args.binary,
        window_size=args.window,
        overlap=args.overlap,
        threshold=args.threshold,
        gap_filling=args.gap_filling,
        min_duration=args.min_duration,
        debug=args.debug
    )
    
    print(f"\nTotal Chronicles Detected: {len(results)}")
    print("\nDetected Chronicles Details:")
    print(json.dumps(results, indent=4, ensure_ascii=False))
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")

