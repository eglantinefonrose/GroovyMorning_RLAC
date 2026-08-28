import json
import argparse
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from main import load_ground_truth
from evaluator import Evaluator

def visualize(gt_data, pred_data, output_path="comparison.png", title="Chronicle Detection Comparison", evaluate=False):
    """
    Creates a timeline visualization of Ground Truth vs Predictions.
    """
    fig, ax = plt.subplots(figsize=(15, 6))
    
    # Track heights
    GT_Y = 2
    PRED_Y = 1
    HEIGHT = 0.6
    
    # Determine the max time for axis scaling
    max_time = 0
    if gt_data:
        max_time = max(max_time, max((c['end'] for c in gt_data), default=0))
    
    if isinstance(pred_data, dict):
        # Already evaluated results
        all_ends = []
        for m in pred_data.get("matches", []):
            all_ends.append(m['pred']['end'])
        for fp in pred_data.get("false_positives", []):
            all_ends.append(fp['end'])
        if all_ends:
            max_time = max(max_time, max(all_ends))
    elif pred_data:
        # Simple list of detections
        max_time = max(max_time, max((c['end'] for c in pred_data), default=0))
    
    if max_time == 0:
        max_time = 3600 # Default to 1 hour if no data
    
    # 1. Plot Ground Truth
    unique_labels = sorted(list(set(c.get('label', 'inconnu') for c in gt_data)))
    cmap = plt.get_cmap('tab20')
    label_to_color = {label: cmap(i % 20) for i, label in enumerate(unique_labels)}

    GT_BAR_DURATION = 2  # Thin tick for the start
    
    for i, c in enumerate(gt_data):
        label = c.get('label', 'inconnu')
        start = c['start']
        color = label_to_color.get(label, 'skyblue')
        
        # Draw a thin bar at the start
        rect = patches.Rectangle((start, GT_Y - HEIGHT/2), GT_BAR_DURATION, HEIGHT, 
                                 linewidth=1, edgecolor='black', facecolor=color, alpha=1.0)
        ax.add_patch(rect)
        
        # Add label
        y_offset = (HEIGHT/2 + 0.1) if i % 2 == 0 else (HEIGHT/2 + 0.5)
        ax.text(start, GT_Y + y_offset, label, 
                horizontalalignment='center', verticalalignment='bottom', fontsize=7, rotation=45)

    # 2. Plot Predictions
    if not evaluate:
        # Default mode (Minimalist): Just show raw blocks in a single color
        all_preds = []
        if isinstance(pred_data, dict):
            if "matches" in pred_data:
                for m in pred_data["matches"]:
                    all_preds.append(m['pred'])
                for fp in pred_data["false_positives"]:
                    all_preds.append(fp)
            elif "detections" in pred_data:
                all_preds = pred_data["detections"]
        else:
            all_preds = pred_data

        for p in all_preds:
            start = p['start']
            duration = p['end'] - p['start']
            rect = patches.Rectangle((start, PRED_Y - HEIGHT/2), duration, HEIGHT, 
                                     linewidth=1, edgecolor='black', facecolor='orange', alpha=0.7)
            ax.add_patch(rect)
    else:
        # Evaluation mode (Detailed: Matches, FP, Missed)
        if isinstance(pred_data, dict) and "matches" in pred_data:
            # Matches (Same color as GT)
            for m in pred_data["matches"]:
                p = m['pred']
                gt = m['gt']
                start = p['start']
                duration = p['end'] - p['start']
                detected_at = p.get('detected_at', start)
                color = label_to_color.get(gt.get('label', 'inconnu'), 'limegreen')
                
                # Draw the prediction box
                rect = patches.Rectangle((start, PRED_Y - HEIGHT/2), duration, HEIGHT, 
                                         linewidth=2, edgecolor='darkgreen', facecolor=color, alpha=0.6)
                ax.add_patch(rect)
                
                # Add a vertical line for the exact detection moment
                ax.vlines(detected_at, PRED_Y - HEIGHT/2, PRED_Y + HEIGHT/2, colors='black', linewidth=2)
                
            # False Positives (Red/Grey)
            for p in pred_data["false_positives"]:
                start = p['start']
                duration = p['end'] - p['start']
                detected_at = p.get('detected_at', start)
                rect = patches.Rectangle((start, PRED_Y - HEIGHT/2), duration, HEIGHT, 
                                         linewidth=1, edgecolor='black', facecolor='red', alpha=0.4)
                ax.add_patch(rect)
                ax.vlines(detected_at, PRED_Y - HEIGHT/2, PRED_Y + HEIGHT/2, colors='black', linewidth=1, linestyle='--')
                
            # Missed (Indicated on GT track with a thick red border)
            for c in pred_data["missed_chronicles"]:
                start = c['start']
                duration = c['end'] - c['start']
                rect = patches.Rectangle((start, GT_Y - HEIGHT/2), duration, HEIGHT, 
                                         linewidth=3, edgecolor='red', facecolor='none', alpha=1.0, linestyle='--')
                ax.add_patch(rect)
        else:
            # Simple list of detections (Orange)
            for p in pred_data:
                start = p['start']
                duration = p['end'] - p['start']
                rect = patches.Rectangle((start, PRED_Y - HEIGHT/2), duration, HEIGHT, 
                                         linewidth=1, edgecolor='darkorange', facecolor='orange', alpha=0.7)
                ax.add_patch(rect)

    # Styling
    ax.set_ylim(0, 3)
    ax.set_xlim(0, max_time * 1.05)
    ax.set_yticks([PRED_Y, GT_Y])
    ax.set_yticklabels(['Prediction', 'Ground Truth'])
    ax.set_xlabel('Time (seconds)')
    ax.set_title(title)
    
    # Grid
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Visualization saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Visualize Chronicle Detection Results")
    parser.add_argument("--gt", required=True, help="Ground Truth file (JSON/TXT)")
    parser.add_argument("--results", required=True, help="Results JSON file")
    parser.add_argument("--output", default="comparison.png", help="Output image file path")
    parser.add_argument("--label-agnostic", action="store_true", help="Ignore labels during evaluation")
    parser.add_argument("--evaluate", action="store_true", help="Show detailed evaluation (TP/FP/FN)")
    
    args = parser.parse_args()
    
    # 1. Load GT
    gt_data = load_ground_truth(args.gt)
    
    # 2. Load Results
    with open(args.results, 'r', encoding='utf-8') as f:
        res_data = json.load(f)
    
    # 3. Check if it's already evaluated
    if isinstance(res_data, dict) and "matches" in res_data:
        print("Detected already evaluated results.")
        pred_data = res_data
    else:
        print("Evaluating raw results before visualization...")
        # Extract detections
        if isinstance(res_data, dict) and "detections" in res_data:
            detections = res_data["detections"]
        elif isinstance(res_data, list):
            detections = res_data
        else:
            print("Error: Could not find detections in results file.")
            return
            
        evaluator = Evaluator(iou_threshold=0.3, label_agnostic=args.label_agnostic)
        pred_data = evaluator.evaluate(detections, gt_data)
        
    # 4. Visualize
    visualize(gt_data, pred_data, output_path=args.output, 
              title=f"Comparison: {os.path.basename(args.results)}",
              evaluate=args.evaluate)

if __name__ == "__main__":
    main()
