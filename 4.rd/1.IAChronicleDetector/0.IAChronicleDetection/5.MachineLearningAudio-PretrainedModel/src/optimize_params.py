import os
import json
import torch
import librosa
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor

SAMPLING_RATE = 16000
AUDIO_PATH = "10075-07.04.2026-ITEMA_24467552-2026C6608S0097-NET_MFC_BE8424AB-0782-4064-B140-DD0480F89F2A-21-0097c3eba2e7ff163fc0dd719431af92.mp3"
MODEL_DIR = "./model_output_beats"
CACHE_FILE = "raw_preds_cache.json"

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

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_raw_predictions():
    if os.path.exists(CACHE_FILE):
        print(f"Loading raw predictions from cache {CACHE_FILE}...")
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
            
    print(f"Loading AST model from {MODEL_DIR}...")
    model = ASTForAudioClassification.from_pretrained(MODEL_DIR)
    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_DIR)
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model.to(device)
    model.eval()

    print(f"Loading audio {AUDIO_PATH}...")
    audio, sr = librosa.load(AUDIO_PATH, sr=SAMPLING_RATE)
    duration = len(audio) / SAMPLING_RATE
    window_size = 10.0
    overlap = 9.0
    step = window_size - overlap
    
    raw_results = []
    print(f"Running sliding window inference (step={step}s)...")
    for start in np.arange(0, duration - window_size, step):
        end = start + window_size
        segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
        inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                 max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
        conf = probs[0][1].item()
        raw_results.append({"start": float(start), "end": float(end), "confidence": float(conf)})
        
        if len(raw_results) % 500 == 0:
            print(f"Processed {start:.1f}s / {duration:.1f}s...")
            
    with open(CACHE_FILE, "w") as f:
        json.dump(raw_results, f)
    return raw_results

def apply_post_processing(raw_predictions, smoothed_probs, threshold, gap_filling, min_duration):
    # 1. Thresholding to create initial segments
    segments = []
    current_start = None
    current_end = None
    
    for i, prob in enumerate(smoothed_probs):
        if prob >= threshold:
            if current_start is None:
                current_start = raw_predictions[i]["start"]
            current_end = raw_predictions[i]["end"]
        else:
            if current_start is not None:
                segments.append({"start": current_start, "end": current_end})
                current_start = None
    if current_start is not None:
        segments.append({"start": current_start, "end": current_end})

    if not segments:
        return []

    # 2. Gap filling: merge segments separated by <= gap_filling
    filled_segments = []
    curr = segments[0].copy()
    for next_seg in segments[1:]:
        if next_seg["start"] - curr["end"] <= gap_filling:
            curr["end"] = next_seg["end"]
        else:
            filled_segments.append(curr)
            curr = next_seg.copy()
    filled_segments.append(curr)
    
    # 3. Min duration filtering
    final_segments = [s for s in filled_segments if (s["end"] - s["start"]) >= min_duration]
    return final_segments

def is_perfect_match(predicted_segments, target_segments):
    if len(predicted_segments) != len(target_segments):
        return False
    
    # Compare with a small tolerance for floating point issues, though 0.1s should be enough
    # given that our window step is 1.0s and targets are integers.
    for p, t in zip(predicted_segments, target_segments):
        if abs(p["start"] - t[0]) > 0.1 or abs(p["end"] - t[1]) > 0.1:
            return False
    return True

def calculate_score(predicted_segments, target_segments):
    if not predicted_segments: return -1000000
    # Strict penalty for count mismatch
    score = -abs(len(predicted_segments) - len(target_segments)) * 10000
    pred_sorted = sorted(predicted_segments, key=lambda x: x["start"])
    target_sorted = sorted(target_segments, key=lambda x: x[0])
    for i in range(min(len(pred_sorted), len(target_sorted))):
        p = pred_sorted[i]
        t = target_sorted[i]
        score -= (p["start"] - t[0])**2
        score -= (p["end"] - t[1])**2
    return score

def main():
    raw_preds = get_raw_predictions()
    
    # Pre-calculate smoothed probabilities to speed up the loop
    print("Pre-calculating median smoothing...")
    window_probs = [p["confidence"] for p in raw_preds]
    kernel_size = 11
    padded_probs = np.pad(window_probs, (kernel_size // 2, kernel_size // 2), mode='edge')
    smoothed_probs = []
    for i in range(len(window_probs)):
        window = padded_probs[i : i + kernel_size]
        smoothed_probs.append(np.median(window))

    print("\nStarting exhaustive search for best parameters (refined step)...")
    
    # Refined search
    thresholds = np.arange(0.0, 1.001, 0.001)
    gap_fillings = np.arange(0.0, 2.01, 0.05) # Slightly larger step for gap to keep execution time reasonable
    min_durations = np.arange(0, 190, 10)
    
    total_iterations = len(thresholds) * len(gap_fillings) * len(min_durations)
    print(f"Total combinations to test: {total_iterations}")
    
    best_score = -float('inf')
    best_params = None
    best_segments = None
    
    perfect_matches = []

    count = 0
    for t in thresholds:
        for g in gap_fillings:
            for m in min_durations:
                processed = apply_post_processing(raw_preds, smoothed_probs, t, g, m)
                
                # Check for perfect match first
                if is_perfect_match(processed, TARGET_SECONDS):
                    perfect_matches.append({"threshold": float(t), "gap_filling": float(g), "min_duration": float(m)})
                
                # Calculate score for proximity
                score = calculate_score(processed, TARGET_SECONDS)
                if score > best_score:
                    best_score = score
                    best_params = {"threshold": float(t), "gap_filling": float(g), "min_duration": float(m)}
                    best_segments = processed
                
                count += 1
                if count % 100000 == 0:
                    print(f"Progress: {count}/{total_iterations} ({(count/total_iterations)*100:.1f}%)")

    if perfect_matches:
        print("\n" + "="*50)
        print(f"FOUND {len(perfect_matches)} PERFECT PARAMETER SETS")
        print(json.dumps(perfect_matches[0], indent=4))
        print("="*50)
        final_params = perfect_matches[0]
    else:
        print("\n" + "="*50)
        print("RESULT: No exact match found. Best approximation:")
        print(f"Score: {best_score:.4f}")
        print(json.dumps(best_params, indent=4))
        print(f"Detected {len(best_segments)} segments vs {len(TARGET_SECONDS)} target.")
        print("="*50)
        final_params = best_params

    # Save output
    formatted_results = []
    for r in (best_segments if best_segments else []):
        formatted_results.append({
            "start": format_time(r["start"]),
            "end": format_time(r["end"])
        })
    
    with open("optimized_params.json", "w", encoding="utf-8") as f:
        json.dump({
            "best_params": final_params, 
            "is_perfect": len(perfect_matches) > 0,
            "detections": formatted_results
        }, f, indent=4)

if __name__ == "__main__":
    main()
