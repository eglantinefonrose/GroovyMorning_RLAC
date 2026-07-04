import json

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
    def __init__(self, iou_threshold=0.5):
        self.iou_threshold = iou_threshold

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

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_iou = sum(ious) / len(ious) if ious else 0.0

        # Overall score (arbitrary combination of IoU and Latency)
        # Latency component: 1.0 if latency < 5s, 0.0 if latency > 60s, linear in between
        latency_score = max(0.0, min(1.0, 1.0 - (avg_latency - 5) / 55)) if latencies else 0.0
        # IoU component: avg_iou
        overall_score = (avg_iou * 0.6 + latency_score * 0.4) * 100 if tp > 0 else 0.0

        results["metrics"] = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "avg_latency": avg_latency,
            "avg_iou": avg_iou,
            "overall_score": overall_score
        }

        return results

if __name__ == "__main__":
    # Quick test
    evaluator = Evaluator()
    preds = [{"label": "test", "start": 10, "end": 20, "detected_at": 12, "confidence": 0.9}]
    gt = [{"label": "test", "start": 10, "end": 20}]
    print(json.dumps(evaluator.evaluate(preds, gt), indent=2))
