import os
import argparse
import pandas as pd
import numpy as np
from src.utils import load_transcription, load_timecodes, format_timecode
from src.evaluation import evaluate_chronicles
from predict import predict

def evaluate_model_precision(srt_path, tc_path, output_csv="results/evaluation_results.csv"):
    """
    Évalue la précision selon la méthode Cardinalité (40%) + Alignement (60%).
    """
    print(f"\n--- Évaluation de précision (Méthode 40/60) ---")
    print(f"SRT: {os.path.basename(srt_path)}")
    print(f"TC:  {os.path.basename(tc_path)}")

    # 1. Prédire les chroniques
    predicted_chronicles = predict(srt_path)
    if predicted_chronicles is None:
        predicted_chronicles = []

    # 2. Charger la vérité terrain
    ground_truth = load_timecodes(tc_path)
    
    # 3. Calculer les métriques
    metrics = evaluate_chronicles(predicted_chronicles, ground_truth)
    
    # 4. Préparer les données détaillées pour le CSV
    detailed_results = []
    for detail in metrics["details"]:
        gt_idx = detail["gt_idx"]
        gt_start, gt_end = ground_truth[gt_idx]
        
        p = None
        if detail["pred_idx"] is not None:
            p = predicted_chronicles[detail["pred_idx"]]
        
        detailed_results.append({
            "chronicle_index": gt_idx + 1,
            "gt_start": format_timecode(gt_start),
            "gt_end": format_timecode(gt_end),
            "detected": "YES" if detail["score"] > 0 else "NO",
            "score_chronique": round(detail["score"], 3),
            "iou": round(detail["iou"], 3),
            "offset_avg_sec": round(detail["offset"], 2) if detail["offset"] is not None else "-",
            "pred_start": format_timecode(p['start']) if p else "-",
            "pred_end": format_timecode(p['end']) if p else "-"
        })

    # 5. Export CSV
    df = pd.DataFrame(detailed_results)
    
    # Ligne de résumé
    summary_row = {
        "chronicle_index": "SUMMARY",
        "gt_start": f"Score Global: {metrics['score_global']}",
        "gt_end": f"Card: {metrics['cardinality_score']}",
        "detected": f"Align: {metrics['alignment_score']}",
        "score_chronique": "",
        "iou": f"GT: {metrics['n_gt']}",
        "offset_avg_sec": f"Pred: {metrics['n_pred']}",
        "pred_start": "",
        "pred_end": ""
    }
    df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    
    print(f"\nRésultats d'évaluation exportés dans : {output_csv}")
    print(f"SCORE GLOBAL : {metrics['score_global']*100}%")
    print(f"  - Cardinalité (40%) : {metrics['cardinality_score']*100}%")
    print(f"  - Alignement (60%)  : {metrics['alignment_score']*100}%")
    
    return metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srt_path", help="Chemin vers le fichier SRT")
    parser.add_argument("tc_path", help="Chemin vers le fichier de Timecodes")
    parser.add_argument("--output", default="results/evaluation_results.csv", help="Fichier CSV de sortie")
    
    args = parser.parse_args()
    evaluate_model_precision(args.srt_path, args.tc_path, args.output)
