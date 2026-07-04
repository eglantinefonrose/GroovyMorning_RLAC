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

def main():
    parser = argparse.ArgumentParser(description="Unified Evaluation Framework")
    parser.add_argument("--audio", help="Path to audio file")
    parser.add_argument("--method", help="Method name (e.g., deepseek)")
    parser.add_argument("--gt", help="Ground Truth file (JSON)")
    parser.add_argument("--buffer", type=int, default=5, help="Buffer size in seconds")
    parser.add_argument("--methods", nargs="*", help="List all available methods or run multiple methods")
    
    args = parser.parse_args()

    if args.methods is not None and len(args.methods) == 0:
        list_available_methods()
        return

    # Determine which methods to run
    methods_to_run = []
    if args.methods:
        methods_to_run = args.methods
    elif args.method:
        methods_to_run = [args.method]

    if not methods_to_run:
        if args.methods is None: # --methods not used at all
             parser.error("You must specify at least one method via --method or --methods.")
        return # already handled above

    if not args.audio or not args.gt:
        parser.error("--audio and --gt are required to run evaluation.")

    # 2. Load Ground Truth
    gt_data = load_ground_truth(args.gt)
    print(f"Loaded {len(gt_data)} chronicles from ground truth.")

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
        evaluator = Evaluator()
        results = evaluator.evaluate(detections, gt_data)
        all_results[method_name] = results

        # 5. Report
        print("\n" + "="*40)
        print(f" EVALUATION REPORT: {method_name} ")
        print("="*40)
        metrics = results["metrics"]
        print(f"Precision:    {metrics['precision']:.2f}")
        print(f"Recall:       {metrics['recall']:.2f}")
        print(f"F1-Score:     {metrics['f1_score']:.2f}")
        print(f"Avg Latency:  {metrics['avg_latency']:.2f}s")
        print(f"Avg IoU:      {metrics['avg_iou']:.2f}")
        print(f"OVERALL SCORE: {metrics['overall_score']:.2f}/100")
        print("="*40)
        
        # Save results
        output_file = f"results_{method_name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Detailed results saved to {output_file}")

        # 6. Matrix Update
        update_evaluation_matrix(method_name, args.audio, metrics['overall_score'])

    if len(methods_to_run) > 1:
        print("\n" + "!"*40)
        print(" COMPARISON SUMMARY ")
        print("!"*40)
        print(f"{'Method':<15} | {'Score':<6} | {'F1':<6} | {'Latency':<8}")
        print("-" * 45)
        for name, res in all_results.items():
            m = res["metrics"]
            print(f"{name:<15} | {m['overall_score']:>6.2f} | {m['f1_score']:>6.2f} | {m['avg_latency']:>7.2f}s")
        print("-" * 45)

if __name__ == "__main__":
    main()
