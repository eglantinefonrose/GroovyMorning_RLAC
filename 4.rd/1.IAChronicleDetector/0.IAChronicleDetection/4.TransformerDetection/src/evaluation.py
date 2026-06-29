import numpy as np
from typing import List, Dict, Tuple

def calculate_iou(range1: Tuple[float, float], range2: Tuple[float, float]) -> float:
    """Intersection over Union."""
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def evaluate_chronicles(predicted: List[Dict[str, float]], ground_truth: List[Tuple[float, float]], max_offset_tolerance: float = 60.0):
    """
    Nouvelle méthode d'évaluation (40% Cardinalité, 60% Alignement Séquentiel).
    """
    n_pred = len(predicted)
    n_gt = len(ground_truth)
    
    if n_gt == 0:
        return {"score_global": 0.0 if n_pred > 0 else 1.0, "cardinality_score": 0.0, "alignment_score": 0.0}

    # 1. SCORE DE CARDINALITÉ (40%)
    # On pénalise la différence entre le nombre attendu et le nombre trouvé
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt)
    
    # 2. SCORE D'ALIGNEMENT SÉQUENTIEL (60%)
    chronicle_scores = []
    pred_used = set()
    matches_info = []

    # On itère sur la vérité terrain (ordre chronologique)
    for i, gt in enumerate(ground_truth):
        gt_start, gt_end = gt
        best_iou = -1
        best_p_idx = -1
        
        # On cherche la meilleure prédiction correspondante non encore utilisée
        for p_idx, p in enumerate(predicted):
            if p_idx in pred_used: continue
            iou = calculate_iou((p['start'], p['end']), gt)
            if iou > best_iou:
                best_iou = iou
                best_p_idx = p_idx
        
        if best_p_idx != -1 and best_iou > 0:
            pred_used.add(best_p_idx)
            p = predicted[best_p_idx]
            
            # Calcul du décalage moyen sur les bornes
            offset = (abs(p['start'] - gt_start) + abs(p['end'] - gt_end)) / 2
            
            # Note de la chronique : décroissance linéaire selon le décalage
            # Si offset = 0 -> 1.0, si offset >= max_offset_tolerance -> 0.0
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
            
            matches_info.append({
                "gt_idx": i,
                "pred_idx": best_p_idx,
                "iou": best_iou,
                "offset": offset,
                "score": ch_score
            })
        else:
            # Chronique manquée
            chronicle_scores.append(0.0)
            matches_info.append({"gt_idx": i, "pred_idx": None, "iou": 0, "offset": None, "score": 0})

    alignment_score = np.mean(chronicle_scores) if chronicle_scores else 0.0
    
    # 3. SCORE GLOBAL
    score_global = (cardinality_score * 0.4) + (alignment_score * 0.6)
    
    return {
        "n_gt": n_gt,
        "n_pred": n_pred,
        "cardinality_score": round(cardinality_score, 3),
        "alignment_score": round(alignment_score, 3),
        "score_global": round(score_global, 3),
        "details": matches_info
    }
