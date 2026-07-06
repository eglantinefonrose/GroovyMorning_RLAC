import json
import statistics

def calculate_iou(pred_start, pred_end, gt_start, gt_end):
    """Calculates Intersection over Union (IoU) for two time intervals."""
    intersection_start = max(pred_start, gt_start)
    intersection_end = min(pred_end, gt_end)
    
    if intersection_start >= intersection_end:
        return 0.0
    
    intersection = intersection_end - intersection_start
    union = (pred_end - pred_start) + (gt_end - gt_start) - intersection
    
    return intersection / union if union > 0 else 0.0

class Evaluator:
    def __init__(self, iou_threshold=0.5, label_agnostic=False):
        self.iou_threshold = iou_threshold
        self.label_agnostic = label_agnostic

    def evaluate(self, predictions, ground_truth):
        """
        Evaluates predictions against ground truth.
        predictions: list of dicts with 'start', 'end', 'detected_at', 'label'
        ground_truth: list of dicts with 'start', 'end', 'label'
        """
        results = {
            "matches": [],
            "false_positives": [],
            "missed_chronicles": [],
            "metrics": {
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "avg_latency": 0.0,
                "overall_score": 0.0
            }
        }

        matched_gt_indices = set()
        latencies = []
        ious = []

        for pred in predictions:
            best_iou = 0
            best_gt_idx = -1
            
            for i, gt in enumerate(ground_truth):
                if i in matched_gt_indices:
                    continue
                
                # Check label matching unless label_agnostic is True
                if not self.label_agnostic and pred.get('label') != gt.get('label'):
                    continue
                
                iou = calculate_iou(pred['start'], pred['end'], gt['start'], gt['end'])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = i
            
            if best_iou >= self.iou_threshold:
                matched_gt_indices.add(best_gt_idx)
                gt = ground_truth[best_gt_idx]
                latency = pred['detected_at'] - gt['start']
                
                match_info = {
                    "pred": pred,
                    "gt": gt,
                    "iou": best_iou,
                    "latency": latency
                }
                results["matches"].append(match_info)
                latencies.append(latency)
                ious.append(best_iou)
            else:
                results["false_positives"].append(pred)

        for i, gt in enumerate(ground_truth):
            if i not in matched_gt_indices:
                results["missed_chronicles"].append(gt)

        # Calculate metrics
        tp = len(results["matches"])
        fp = len(results["false_positives"])
        fn = len(results["missed_chronicles"])
        total_gt = len(ground_truth)
        total_pred = len(predictions)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Enhanced Statistics
        def get_stats(data):
            if not data:
                return {"avg": 0.0, "min": 0.0, "max": 0.0, "median": 0.0, "std": 0.0}
            return {
                "avg": sum(data) / len(data),
                "min": min(data),
                "max": max(data),
                "median": statistics.median(data),
                "std": statistics.stdev(data) if len(data) > 1 else 0.0
            }

        latency_stats = get_stats(latencies)
        iou_stats = get_stats(ious)

        avg_latency = latency_stats["avg"]
        avg_iou = iou_stats["avg"]

        # Overall score (arbitrary combination of IoU and Latency)
        # Latency component: 1.0 if latency < 5s, 0.0 if latency > 60s, linear in between
        latency_score = max(0.0, min(1.0, 1.0 - (avg_latency - 5) / 55)) if latencies else 0.0
        # IoU component: avg_iou
        overall_score = (avg_iou * 0.6 + latency_score * 0.4) * 100 if tp > 0 else 0.0

        # Breakdown by label
        label_metrics = {}
        if not self.label_agnostic:
            # Get all unique labels from both GT and Predictions
            all_labels = set(gt.get('label') for gt in ground_truth) | set(p.get('label') for p in predictions if p.get('label'))
            
            for label in all_labels:
                label_gt = [gt for gt in ground_truth if gt.get('label') == label]
                label_matches = [m for m in results["matches"] if m['gt'].get('label') == label]
                # A false positive is assigned to a label if it HAS that label but didn't match anything
                label_fp = [fp for fp in results["false_positives"] if fp.get('label') == label]
                
                tp_l = len(label_matches)
                fp_l = len(label_fp)
                fn_l = len(label_gt) - tp_l
                
                prec_l = tp_l / (tp_l + fp_l) if (tp_l + fp_l) > 0 else 0.0
                rec_l = tp_l / (tp_l + fn_l) if (tp_l + fn_l) > 0 else 0.0
                f1_l = 2 * (prec_l * rec_l) / (prec_l + rec_l) if (prec_l + rec_l) > 0 else 0.0
                
                label_metrics[label] = {
                    "total_gt": len(label_gt),
                    "tp": tp_l,
                    "fp": fp_l,
                    "fn": fn_l,
                    "precision": prec_l,
                    "recall": rec_l,
                    "f1_score": f1_l
                }

        results["metrics"] = {
            "total_gt": total_gt,
            "total_pred": total_pred,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "avg_latency": avg_latency,
            "avg_iou": avg_iou,
            "latency_stats": latency_stats,
            "iou_stats": iou_stats,
            "label_metrics": label_metrics,
            "latency_score": latency_score,
            "overall_score": overall_score
        }

        return results

if __name__ == "__main__":
    # Quick test
    evaluator = Evaluator()
    preds = [{"label": "test", "start": 10, "end": 20, "detected_at": 12, "confidence": 0.9}]
    gt = [{"label": "test", "start": 10, "end": 20}]
    print(json.dumps(evaluator.evaluate(preds, gt), indent=2))
