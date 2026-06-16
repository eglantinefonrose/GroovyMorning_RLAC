import os
import argparse
import json
import sys
import glob
import numpy as np

# Add src directory to path for imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from predict_robust import predict_robust

def find_file_robustly(original_path):
    if not original_path: return None
    if os.path.exists(original_path): return original_path
    filename = os.path.basename(original_path)
    # Common alternate names
    alt_filename = filename.replace("transcription_chronique", "timecode_chronique").replace("timecode_chronique", "transcription_chronique")
    
    # Search in common locations
    for depth in ["./", "../", "../../", "../../../", "../../../../"]:
        assets_dir = os.path.join(depth, "@assets")
        if os.path.exists(assets_dir):
            for fname in [filename, alt_filename]:
                matches = glob.glob(os.path.join(assets_dir, "**", fname), recursive=True)
                if matches: return matches[0]
    
    # Also check current directory
    if os.path.exists(filename): return filename
    
    return original_path

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def parse_time(time_str):
    """Parses HH:MM:SS.mmm or MM:SS or seconds as float/string."""
    try:
        if isinstance(time_str, (int, float)):
            return float(time_str)
        
        if ':' not in time_str:
            return float(time_str)
            
        parts = time_str.split(':')
        if len(parts) == 3: # HH:MM:SS.mmm
            h, m, s = parts
            if '.' in s:
                s, ms = s.split('.')
                return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))
            else:
                return int(h) * 3600 + int(m) * 60 + int(s)
        elif len(parts) == 2: # MM:SS.mmm
            m, s = parts
            if '.' in s:
                s, ms = s.split('.')
                return int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))
            else:
                return int(m) * 60 + int(s)
    except Exception as e:
        print(f"Warning: Could not parse time '{time_str}': {e}")
        return 0.0
    return 0.0

def load_ground_truth(tc_path):
    tc_path = find_file_robustly(tc_path)
    if not os.path.exists(tc_path):
        print(f"Error: Ground truth file not found at {tc_path}")
        return []
    
    gt_intervals = []
    with open(tc_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            # Support different formats:
            # 1. start|end
            # 2. HH:MM:SS - HH:MM:SS
            # 3. JSON?
            
            if '|' in line:
                parts = line.split('|')
                gt_intervals.append((parse_time(parts[0]), parse_time(parts[1])))
            elif ' - ' in line:
                parts = line.split(' - ')
                gt_intervals.append((parse_time(parts[0]), parse_time(parts[1])))
            else:
                # Try to see if it's just two space-separated values
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        gt_intervals.append((parse_time(parts[0]), parse_time(parts[1])))
                    except:
                        pass
    
    return gt_intervals

def evaluate_quality(model_dir, audio_path, tc_path, model_type="ast", params=None):
    if not os.path.exists(model_dir):
        print(f"Error: Model directory '{model_dir}' does not exist.")
        return

    audio_path = find_file_robustly(audio_path)
    if not os.path.exists(audio_path):
        print(f"Error: Audio file '{audio_path}' does not exist.")
        return

    print(f"\n--- Robust Evaluation for {model_dir} ---")
    print(f"Audio: {os.path.basename(audio_path)}")
    print(f"Model Type: {model_type}")
    
    # 1. Predict using predict_robust
    robust_args = {
        "audio_path": audio_path,
        "model_type": model_type,
        "model_dir": model_dir
    }
    if params:
        robust_args.update(params)
        
    print(f"Running inference with params: {params if params else 'defaults'}")
    predictions = predict_robust(**robust_args)
    pred_intervals = [(parse_time(p['start']), parse_time(p['end'])) for p in predictions]

    print(f"\n--- Detected {len(predictions)} Chronicles ---")
    for p in predictions:
        print(f"[{p['start']} -> {p['end']}] Confidence: {p['confidence']}")

    # 2. Load Ground Truth
    gt_intervals = load_ground_truth(tc_path)
    if not gt_intervals:
        print("Error: No ground truth intervals loaded. Check your tc_path.")
        return

    print(f"\n--- Ground Truth: {len(gt_intervals)} Chronicles ---")

    # 3. Calculate Metrics (similar to evaluate_quality.py)
    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    
    # Cardinality Score (40%)
    # Penalty if number of detected segments differs from ground truth
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    
    # Alignment Score (60%)
    chronicle_scores = []
    pred_used = set()
    max_offset_tolerance = 30.0 # Seconds

    for gt in gt_intervals:
        best_iou = -1
        best_p_idx = -1
        for p_idx, p in enumerate(pred_intervals):
            if p_idx in pred_used: continue
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_p_idx = p_idx
        
        if best_p_idx != -1 and best_iou > 0:
            pred_used.add(best_p_idx)
            p = pred_intervals[best_p_idx]
            # Alignment is based on IoU and boundary proximity
            start_off = abs(p[0] - gt[0])
            end_off = abs(p[1] - gt[1])
            offset_score = max(0.0, 1.0 - (start_off + end_off) / (2 * max_offset_tolerance))
            
            # Combine IoU and offset
            ch_score = (best_iou * 0.7) + (offset_score * 0.3)
            chronicle_scores.append(ch_score)
        else:
            chronicle_scores.append(0.0)

    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    
    # Penalize extra predictions not matched to ground truth
    extra_preds = n_pred - len(pred_used)
    if n_pred > 0:
        extra_penalty = (extra_preds / n_pred) * 0.2
        alignment_score = max(0.0, alignment_score - extra_penalty)

    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*50)
    print(f"📊 FINAL QUALITY SCORE : {global_score*100:.1f}/100")
    print("="*50)
    print(f"- Cardinality (40%) : {cardinality_score*100:.1f}% ({n_pred} vs {n_gt})")
    print(f"- Temporal Alignment (60%) : {alignment_score*100:.1f}%")
    print("="*50)
    
    return {
        "global_score": global_score,
        "cardinality": cardinality_score,
        "alignment": alignment_score,
        "n_pred": n_pred,
        "n_gt": n_gt
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate model quality using robust inference.")
    parser.add_argument("model_dir", help="Directory containing the trained model")
    parser.add_argument("audio_path", help="Path to the audio file for testing")
    parser.add_argument("tc_path", help="Path to the ground truth timecodes file")
    parser.add_argument("--model_type", default="ast", choices=["wav2vec2", "ast", "beats", "wavlm"], help="Type of model architecture")
    
    # Robust parameters
    parser.add_argument("--threshold_start", type=float, default=0.7)
    parser.add_argument("--threshold_end", type=float, default=0.3)
    parser.add_argument("--window", type=float, default=10.0)
    parser.add_argument("--overlap", type=float, default=8.0)
    parser.add_argument("--smooth_window", type=int, default=3)
    parser.add_argument("--min_duration", type=float, default=10.0)
    
    parser.add_argument("--params_json", help="Optional JSON file containing optimized parameters")
    
    args = parser.parse_args()
    
    params = {
        "threshold_start": args.threshold_start,
        "threshold_end": args.threshold_end,
        "window_size": args.window,
        "overlap": args.overlap,
        "smooth_window": args.smooth_window,
        "min_duration": args.min_duration
    }
    
    if args.params_json and os.path.exists(args.params_json):
        with open(args.params_json, 'r') as f:
            data = json.load(f)
            # The format might be different depending on how it was saved
            if "best_params" in data:
                opt = data["best_params"]
                # Map keys if necessary
                if "threshold" in opt: params["threshold_start"] = opt["threshold"]
                if "gap_filling" in opt: params["overlap"] = params["window_size"] - 0.5 # heuristic if gap_filling used
                if "min_duration" in opt: params["min_duration"] = opt["min_duration"]
            else:
                params.update(data)

    evaluate_quality(
        model_dir=args.model_dir,
        audio_path=args.audio_path,
        tc_path=args.tc_path,
        model_type=args.model_type,
        params=params
    )
