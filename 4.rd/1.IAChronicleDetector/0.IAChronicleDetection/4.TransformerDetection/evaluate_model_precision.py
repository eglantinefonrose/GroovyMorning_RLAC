import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from src.utils import load_transcription, load_timecodes, format_timecode
from src.evaluation import evaluate_chronicles
from predict import predict

def log_to_models_readme(metrics, srt_path, readme_path="models/README.md"):
    """Met à jour le score de performance dans le README du dossier models."""
    if not os.path.exists(readme_path):
        return
        
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = os.path.basename(srt_path)
    
    log_line = (
        f"| {date_str} | {filename} | **{round(metrics['score_global']*100, 1)}%** | "
        f"{round(metrics['cardinality_score']*100, 1)}% | {round(metrics['alignment_score']*100, 1)}% | "
        f"{metrics['n_pred']}/{metrics['n_gt']} |\n"
    )
    
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # On définit la section de score
    section_header = "## Score de Performance (Dernière Évaluation)"
    
    # Si la section existe déjà, on coupe tout ce qui suit pour la remplacer
    if section_header in content:
        base_content = content.split(section_header)[0].rstrip()
    else:
        base_content = content.rstrip()

    new_content = base_content + "\n\n" + section_header + "\n\n"
    new_content += "| Date | Fichier | Score Global | Cardinalité | Alignement | Détail (Pred/GT) |\n"
    new_content += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    new_content += log_line
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Score de performance mis à jour dans {readme_path}")

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
        
        # Détermination du statut selon les seuils du README
        score = detail["score"]
        if score > 0.95:
            statut = "PARFAITE"
        elif score >= 0.70:
            statut = "ACCEPTABLE"
        elif score > 0:
            statut = "IMPRÉCISE"
        else:
            statut = "MISS"

        detailed_results.append({
            "chronicle_index": gt_idx + 1,
            "gt_start": format_timecode(gt_start),
            "gt_end": format_timecode(gt_end),
            "statut": statut,
            "score_chronique": round(score * 100, 1),  # Affichage en %
            "offset_avg_sec": round(detail["offset"], 2) if detail["offset"] is not None else "-",
            "iou": round(detail["iou"], 3),
            "pred_start": format_timecode(p['start']) if p else "-",
            "pred_end": format_timecode(p['end']) if p else "-"
        })

    # 5. Export CSV
    df = pd.DataFrame(detailed_results)
    
    # Ligne de résumé
    summary_row = {
        "chronicle_index": "SUMMARY",
        "gt_start": f"Score Global: {round(metrics['score_global']*100, 1)}%",
        "gt_end": f"Card: {round(metrics['cardinality_score']*100, 1)}%",
        "statut": f"Align: {round(metrics['alignment_score']*100, 1)}%",
        "score_chronique": "",
        "offset_avg_sec": f"Pred/GT: {metrics['n_pred']}/{metrics['n_gt']}",
        "iou": "",
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
    
    # Consigner dans l'historique des modèles
    log_to_models_readme(metrics, srt_path)
    
    return metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srt_path", help="Chemin vers le fichier SRT")
    parser.add_argument("tc_path", help="Chemin vers le fichier de Timecodes")
    parser.add_argument("--output", default="results/evaluation_results.csv", help="Fichier CSV de sortie")
    
    args = parser.parse_args()
    evaluate_model_precision(args.srt_path, args.tc_path, args.output)
