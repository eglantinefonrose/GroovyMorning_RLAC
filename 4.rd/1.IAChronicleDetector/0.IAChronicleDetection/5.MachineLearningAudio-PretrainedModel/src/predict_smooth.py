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

SAMPLING_RATE = 16000

MODEL_CONFIGS = {
    "ast": {
        "dir": "./model_output_ast",
        "model_class": ASTForAudioClassification,
        "extractor_class": ASTFeatureExtractor
    },
    "wav2vec2": {
        "dir": "./model_output",
        "model_class": Wav2Vec2ForSequenceClassification,
        "extractor_class": Wav2Vec2FeatureExtractor
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
    },
    "cnn": {
        "dir": "./model_output_cnn",
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

def predict_smooth(audio_path: str, model_type: str, model_dir: str = None,
                  window_size: float = 10.0, overlap: float = 5.0, 
                  threshold: float = 0.5, smooth_window: int = 5, 
                  min_duration: float = 5.0, debug: bool = False):
    
    config = MODEL_CONFIGS.get(model_type, MODEL_CONFIGS["ast"])
    if not model_dir:
        model_dir = config["dir"]
        
    print(f"Loading {model_type} model from {model_dir}...")
    model = config["model_class"].from_pretrained(model_dir)
    feature_extractor = config["extractor_class"].from_pretrained(model_dir)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device)
    model.eval()

    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    step = window_size - overlap
    
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
             inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", padding=True)
        
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        
        # Prob de la classe 'chronique' (index 1)
        raw_probs.append(probs[0][1].item())
        timestamps.append(start)

    # Application de la Moyenne Mobile (Lissage)
    smoothed_probs = np.convolve(raw_probs, np.ones(smooth_window)/smooth_window, mode='same')

    # Segmentation basée sur le seuil unique
    detected_segments = []
    is_active = False
    current_start = 0
    
    for i in range(len(smoothed_probs)):
        prob = smoothed_probs[i]
        time = timestamps[i]
        
        if not is_active and prob >= threshold:
            is_active = True
            current_start = time
        elif is_active and (prob < threshold or i == len(smoothed_probs) - 1):
            is_active = False
            current_end = time + (window_size / 2)
            if (current_end - current_start) >= min_duration:
                detected_segments.append({
                    "label": "chronique",
                    "start": format_time(current_start),
                    "end": format_time(current_end),
                    "confidence": round(float(np.max(smoothed_probs[max(0, i-5):i+1])), 3)
                })

    if debug:
        for i in range(len(raw_probs)):
             print(f"Time: {format_time(timestamps[i])} | Prob: {raw_probs[i]:.3f} | Smoothed: {smoothed_probs[i]:.3f}")

    return detected_segments

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoothed prediction with Moving Average.")
    parser.add_argument("audio", type=str)
    parser.add_argument("--model_type", type=str, default="ast")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--smooth_window", type=int, default=5)
    parser.add_argument("--window", type=float, default=10.0)
    parser.add_argument("--overlap", type=float, default=5.0)
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    results = predict_smooth(
        audio_path=args.audio,
        model_type=args.model_type,
        threshold=args.threshold,
        smooth_window=args.smooth_window,
        window_size=args.window,
        overlap=args.overlap,
        debug=args.debug
    )
    
    print(f"\nTotal Detected: {len(results)}")
    print(json.dumps(results, indent=4, ensure_ascii=False))
