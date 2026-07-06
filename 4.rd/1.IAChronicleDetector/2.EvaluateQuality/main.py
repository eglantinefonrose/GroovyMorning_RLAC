import argparse
import json
import importlib
import sys
import os
import csv
from evaluator import Evaluator
from simulator import AudioSimulator

def update_evaluation_matrix(method_name, audio_path, score):
    matrix_file = "evaluation_matrix.csv"
    audio_filename = os.path.basename(audio_path)
    
    # 1. Read existing data
    rows = []
    headers = ["Method"]
    if os.path.exists(matrix_file):
        with open(matrix_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)
    
    # 2. Add audio header if it doesn't exist
    if audio_filename not in headers:
        headers.append(audio_filename)
    
    # 3. Find or create the row for the method
    method_row = next((r for r in rows if r["Method"] == method_name), None)
    if not method_row:
        method_row = {"Method": method_name}
        rows.append(method_row)
    
    # 4. Update the score
    method_row[audio_filename] = f"{score:.2f}"
    
    # 5. Write the file
    with open(matrix_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            # Ensure all headers exist in each row
            row_to_write = {h: r.get(h, "") for h in headers}
            writer.writerow(row_to_write)
    
    print(f"Global results updated in {matrix_file}")

def apply_soft_scoring(results):
    """Applies a less strict scoring system to the evaluation results."""
    metrics = results["metrics"]
    if not results.get("matches"):
        metrics["overall_score"] = 0.0
        return results

    # 1. More permissive Latency Score (0 to 120s instead of 0 to 60s)
    # 1.0 if latency < 10s, 0.0 if latency > 120s, linear in between
    avg_latency = metrics.get("avg_latency", 0)
    soft_latency_score = max(0.0, min(1.0, 1.0 - (avg_latency - 10) / 110))
    metrics["soft_latency_score"] = soft_latency_score
    
    # 2. Weighted Score including F1-Score (to reward reliability/recall)
    avg_iou = metrics.get("avg_iou", 0)
    f1 = metrics.get("f1_score", 0)
    
    # New formula: F1 * (60% IoU + 40% Latency) * 100
    # This rewards methods that find the chronicles even if timing isn't perfect
    soft_score = f1 * (avg_iou * 0.6 + soft_latency_score * 0.4) * 100
    metrics["overall_score"] = soft_score
    return results

def load_ground_truth(file_path):
    if file_path.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Expected format: list of {"label": "...", "start": ..., "end": ...}
            # If it's the other format (timecodes), we need to convert.
            if isinstance(data, dict) and "chroniques" in data:
                return convert_gt_format(data["chroniques"])
            return data
    else:
        return parse_text_gt(file_path)

def parse_text_gt(file_path):
    converted = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Format: [HH:MM:SS.mmm] - [HH:MM:SS.mmm] label
            try:
                parts = line.split(']')
                if len(parts) >= 3:
                    start_tc = parts[0].strip('[')
                    end_tc = parts[1].split('[')[-1]
                    label = parts[2].strip(' -')
                    
                    start = timecode_to_seconds(start_tc)
                    end = timecode_to_seconds(end_tc)
                    
                    if start is not None and end is not None:
                        converted.append({
                            "label": label,
                            "start": start,
                            "end": end
                        })
            except Exception as e:
                print(f"Error parsing line: {line} - {e}")
    return converted

def timecode_to_seconds(timecode):
    """Converts HH:MM:SS,mmm or HH:MM:SS.mmm to seconds."""
    if timecode == "inconnu":
        return None
    try:
        # Strip brackets and extra whitespace
        timecode = timecode.strip('[] ')
        parts = timecode.replace(',', '.').split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return float(timecode)
    except Exception:
        return None

def convert_gt_format(chroniques):
    converted = []
    for c in chroniques:
        start = timecode_to_seconds(c.get("timecode_debut"))
        end = timecode_to_seconds(c.get("timecode_fin"))
        if start is not None and end is not None:
            converted.append({
                "label": c.get("nom", "inconnu"),
                "start": start,
                "end": end
            })
    return converted

def list_available_methods():
    methods_dir = os.path.join(os.path.dirname(__file__), "methods")
    if not os.path.exists(methods_dir):
        print("Methods directory not found.")
        return
    
    methods = []
    for file in os.listdir(methods_dir):
        if file.endswith("_wrapper.py"):
            methods.append(file.replace("_wrapper.py", ""))
    
    if not methods:
        print("No methods found in 'methods/' directory.")
    else:
        print("Available methods:")
        for m in sorted(methods):
            print(f" - {m}")

def print_report(method_name, results):
    print("\n" + "="*40)
    print(f" EVALUATION REPORT: {method_name} ")
    print("="*40)
    metrics = results["metrics"]
    
    print(f"--- DETECTIONS COUNTS ---")
    print(f"Ground Truth:    {metrics.get('total_gt', 0)}")
    print(f"Predictions:     {metrics.get('total_pred', 0)}")
    print(f"True Positives:  {metrics.get('tp', 0)}")
    print(f"False Positives: {metrics.get('fp', 0)}")
    print(f"Missed (FN):     {metrics.get('fn', 0)}")
    
    print(f"\n--- PERFORMANCE METRICS ---")
    print(f"Precision:    {metrics['precision']:.2f}")
    print(f"Recall:       {metrics['recall']:.2f}")
    print(f"F1-Score:     {metrics['f1_score']:.2f}")
    
    if "latency_stats" in metrics:
        ls = metrics["latency_stats"]
        print(f"\n--- LATENCY STATISTICS ---")
        print(f"Average:   {ls['avg']:.2f}s")
        print(f"Median:    {ls['median']:.2f}s")
        print(f"Min / Max: {ls['min']:.2f}s / {ls['max']:.2f}s")
        print(f"Std Dev:   {ls['std']:.2f}s")
    else:
        print(f"Avg Latency:  {metrics['avg_latency']:.2f}s")

    if "iou_stats" in metrics:
        is_stats = metrics["iou_stats"]
        print(f"\n--- IOU STATISTICS ---")
        print(f"Average:   {is_stats['avg']:.2f}")
        print(f"Median:    {is_stats['median']:.2f}")
        print(f"Min / Max: {is_stats['min']:.2f} / {is_stats['max']:.2f}")
        print(f"Std Dev:   {is_stats['std']:.2f}")
    else:
        print(f"Avg IoU:      {metrics['avg_iou']:.2f}")
    
    if metrics.get("label_metrics"):
        print(f"\n--- PER-LABEL BREAKDOWN ---")
        print(f"{'Label':<30} | {'GT':<2} | {'TP':<2} | {'FP':<2} | {'F1':<5}")
        print("-" * 50)
        # Sort by F1 score ascending to show problematic labels first
        sorted_labels = sorted(metrics["label_metrics"].items(), key=lambda x: x[1]['f1_score'])
        for label, l_m in sorted_labels:
            print(f"{label[:30]:<30} | {l_m['total_gt']:<2} | {l_m['tp']:<2} | {l_m['fp']:<2} | {l_m['f1_score']:>5.2f}")

    print(f"\n--- SCORE BREAKDOWN (Soft Scoring) ---")
    print(f"Reliability (F1):    {metrics['f1_score']:.2f}")
    print(f"Timing (Avg IoU):    {metrics['avg_iou']:.2f} (Weight: 60%)")
    # soft_latency_score might not be present if apply_soft_scoring wasn't called or failed
    latency_score = metrics.get('soft_latency_score', metrics.get('latency_score', 0))
    print(f"Rapidity (Latency): {latency_score:.2f} (Weight: 40%)")
    print(f"Formula: F1 * (0.6*IoU + 0.4*Latency) * 100")
    
    print(f"\nOVERALL SCORE: {metrics['overall_score']:.2f}/100")
    print("="*40)

def print_comparison_summary(all_results):
    print("\n" + "!"*40)
    print(" COMPARISON SUMMARY ")
    print("!"*40)
    print(f"{'Method':<15} | {'Score':<6} | {'F1':<6} | {'Latency':<8}")
    print("-" * 45)
    for name, res in all_results.items():
        m = res["metrics"]
        print(f"{name:<15} | {m['overall_score']:>6.2f} | {m['f1_score']:>6.2f} | {m['avg_latency']:>7.2f}s")
    print("-" * 45)

def main():
    parser = argparse.ArgumentParser(description="Unified Evaluation Framework")
    parser.add_argument("--audio", help="Path to audio file")
    parser.add_argument("--method", help="Method name (e.g., deepseek)")
    parser.add_argument("--gt", help="Ground Truth file (JSON/TXT)")
    parser.add_argument("--results", help="Path to a pre-existing results JSON file to evaluate")
    parser.add_argument("--audioname", help="Explicit name of the audio for the evaluation matrix")
    parser.add_argument("--buffer", type=int, default=5, help="Buffer size in seconds")
    parser.add_argument("--methods", nargs="*", help="List all available methods or run multiple methods")
    parser.add_argument("--label-agnostic", action="store_true", help="Ignore labels during evaluation (match only by time)")
    
    args = parser.parse_args()

    if args.methods is not None and len(args.methods) == 0:
        list_available_methods()
        return

    # 1. Load Ground Truth (required for evaluation)
    if not args.gt:
        parser.error("--gt is required to run evaluation.")
    gt_data = load_ground_truth(args.gt)
    print(f"Loaded {len(gt_data)} chronicles from ground truth.")

    # 2. Mode d'évaluation de résultats pré-existants
    if args.results:
        if not args.method:
            parser.error("--method is required when using --results to identify the method in the matrix.")
        
        print(f"\n--- Evaluating Pre-existing Results for Method: {args.method} ---")
        try:
            with open(args.results, 'r', encoding='utf-8') as f:
                res_data = json.load(f)
            
            # Extraction des détections (supporte différents formats)
            if isinstance(res_data, dict):
                if "detections" in res_data:
                    detections = res_data["detections"]
                elif "matches" in res_data and "false_positives" in res_data:
                    # Format deepseek/live_transcription custom
                    detections = res_data["matches"] + res_data["false_positives"]
                else:
                    print("Error: Results file format not recognized (dict without 'detections' or 'matches/false_positives').")
                    return
            elif isinstance(res_data, list):
                detections = res_data
            else:
                print("Error: Results file format not recognized (expected list or dict).")
                return

            # Évaluation
            is_label_agnostic = args.label_agnostic or (args.method == "live_transcription")
            # Using a more permissive IoU threshold of 0.3
            evaluator = Evaluator(iou_threshold=0.3, label_agnostic=is_label_agnostic)
            results = evaluator.evaluate(detections, gt_data)
            results = apply_soft_scoring(results)
            
            # Report
            print_report(args.method, results)
            
            # Update Matrix (Priority: --audioname > --audio > results filename)
            if args.audioname:
                csv_id = args.audioname
            elif args.audio:
                csv_id = args.audio
            else:
                csv_id = os.path.basename(args.results)
                
            update_evaluation_matrix(args.method, csv_id, results["metrics"]['overall_score'])
            
            return
            
        except Exception as e:
            print(f"Error evaluating results file: {e}")
            return

    # Determine which methods to run (Standard Simulation Mode)
    methods_to_run = []
    if args.methods:
        methods_to_run = args.methods
    elif args.method:
        methods_to_run = [args.method]

    if not methods_to_run:
        if args.methods is None: # --methods not used at all
             parser.error("You must specify at least one method via --method or --methods, or use --results.")
        return

    if not args.audio:
        parser.error("--audio is required for simulation mode.")

    all_results = {}

    for method_name in methods_to_run:
        # Nettoyage du nom de la méthode (remplace - par _)
        method_name = method_name.replace("-", "_")
        
        print(f"\n--- Running Evaluation for Method: {method_name} ---")
        # 1. Load Method Wrapper
        try:
            module_path = f"methods.{method_name}_wrapper"
            method_module = importlib.import_module(module_path)
            method_wrapper = method_module.Wrapper()
        except Exception as e:
            print(f"Error loading method '{method_name}': {e}")
            continue

        # 3. Run Simulation
        simulator = AudioSimulator(args.audio, buffer_size_seconds=args.buffer)
        detections = simulator.simulate(method_wrapper)
        print(f"Detection finished. {len(detections)} items detected.")

        # 4. Evaluate
        # Mode label_agnostic pour live_transcription (pas de noms de chroniques)
        is_label_agnostic = args.label_agnostic or (method_name == "live_transcription")
        # Using a more permissive IoU threshold of 0.3
        evaluator = Evaluator(iou_threshold=0.3, label_agnostic=is_label_agnostic)
        results = evaluator.evaluate(detections, gt_data)
        results = apply_soft_scoring(results)
        all_results[method_name] = results

        # 5. Report
        print_report(method_name, results)
        
        # 6. Matrix Update
        csv_id = args.audioname if args.audioname else args.audio
        update_evaluation_matrix(method_name, csv_id, results["metrics"]['overall_score'])

    if len(methods_to_run) > 1:
        print_comparison_summary(all_results)

if __name__ == "__main__":
    main()
