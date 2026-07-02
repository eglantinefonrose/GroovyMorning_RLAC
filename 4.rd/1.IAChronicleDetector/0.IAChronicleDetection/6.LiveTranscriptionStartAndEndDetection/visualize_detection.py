import os
import argparse
import re
import webbrowser
from difflib import SequenceMatcher
from inference_2 import ChronicleDetectorV2
from inference_live_sim import LiveChronicleDetector
from inference import clean_srt_content

def string_similarity(a, b):
    """Calcule la similitude entre deux chaînes (0.0 à 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def generate_html_report(sentences_data, output_path, transcription_name, stats):
    """
    Génère un rapport HTML visualisant les détections.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Rapport de Détection - {transcription_name}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; margin: 0; background: #f0f2f5; color: #333; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }}
            .container {{ max-width: 1100px; margin: 20px auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
            h1 {{ margin: 0 0 10px 0; font-size: 1.8em; }}
            .file-info {{ opacity: 0.8; font-size: 0.9em; }}
            
            .stats-bar {{ display: flex; justify-content: space-around; margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef; }}
            .stat-card {{ text-align: center; }}
            .stat-value {{ display: block; font-size: 1.5em; font-weight: bold; color: #2c3e50; }}
            .stat-label {{ font-size: 0.8em; color: #6c757d; text-transform: uppercase; }}
            
            .legend {{ margin: 20px 0; padding: 15px; border-radius: 8px; background: #fff; border: 1px dashed #ccc; display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; }}
            .legend-item {{ display: flex; align-items: center; font-size: 0.9em; }}
            .dot {{ height: 14px; width: 14px; border-radius: 3px; display: inline-block; margin-right: 8px; }}
            
            .text-content {{ white-space: pre-wrap; font-size: 1.1em; color: #444; border-top: 1px solid #eee; padding-top: 20px; }}
            
            .sentence {{ padding: 2px 0; border-bottom: 2px solid transparent; transition: all 0.2s; }}
            .tp {{ background-color: #d4edda; border-bottom: 2px solid #28a745; color: #155724; font-weight: 500; }}
            .fp {{ background-color: #f8d7da; border-bottom: 2px solid #dc3545; color: #721c24; font-weight: 500; }}
            .fn {{ border-bottom: 3px solid #007bff; background-color: #e7f1ff; color: #004085; font-weight: 500; }}
            .tn {{ color: #777; }}
            
            .sentence:hover {{ background-color: #ffff99; cursor: pointer; }}
            
            /* Tooltip amélioré */
            .tooltip {{ position: relative; }}
            .tooltip .tooltiptext {{
                visibility: hidden; width: 350px; background-color: #2c3e50; color: #fff; text-align: left;
                border-radius: 8px; padding: 12px; position: absolute; z-index: 100; bottom: 125%; left: 50%;
                transform: translateX(-50%); opacity: 0; transition: opacity 0.3s; box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                font-weight: normal; font-size: 0.85em; line-height: 1.4;
            }}
            .sentence:hover .tooltiptext {{ visibility: visible; opacity: 1; }}
            .tooltip .tooltiptext::after {{
                content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px;
                border-width: 5px; border-style: solid; border-color: #2c3e50 transparent transparent transparent;
            }}
            
            .meta-info {{ border-top: 1px solid #444; margin-top: 8px; padding-top: 8px; font-size: 0.9em; opacity: 0.9; }}
            .label-tp {{ color: #2ecc71; font-weight: bold; }}
            .label-fp {{ color: #e74c3c; font-weight: bold; }}
            .label-fn {{ color: #3498db; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Détection des débuts de chroniques</h1>
            <div class="file-info">{transcription_name}</div>
        </div>
        
        <div class="container">
            <div class="stats-bar">
                <div class="stat-card">
                    <span class="stat-value">{stats['tp']}</span>
                    <span class="stat-label">Vrais Positifs</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value" style="color: #e74c3c;">{stats['fp']}</span>
                    <span class="stat-label">Faux Positifs</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value" style="color: #3498db;">{stats['fn']}</span>
                    <span class="stat-label">Oublis (FN)</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{stats['precision']:.2f}</span>
                    <span class="stat-label">Précision</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{stats['recall']:.2f}</span>
                    <span class="stat-label">Rappel</span>
                </div>
            </div>
            
            <div class="legend">
                <div class="legend-item"><span class="dot" style="background-color: #d4edda; border-bottom: 2px solid #28a745;"></span> <strong>Vrai Positif</strong> (Détecté & GT)</div>
                <div class="legend-item"><span class="dot" style="background-color: #f8d7da; border-bottom: 2px solid #dc3545;"></span> <strong>Faux Positif</strong> (Détecté mais pas GT)</div>
                <div class="legend-item"><span class="dot" style="background-color: #e7f1ff; border-bottom: 3px solid #007bff;"></span> <strong>Faux Négatif</strong> (GT non détecté)</div>
                <div class="legend-item"><span class="dot" style="background-color: #eee;"></span> Texte normal</div>
            </div>

            <div class="text-content">"""

    for s in sentences_data:
        cls = "tn"
        status_label = "Texte normal"
        status_class = ""
        
        if s['is_detected'] and s['is_gt']:
            cls = "tp"
            status_label = "Vrai Positif"
            status_class = "label-tp"
        elif s['is_detected'] and not s['is_gt']:
            cls = "fp"
            status_label = "Faux Positif"
            status_class = "label-fp"
        elif not s['is_detected'] and s['is_gt']:
            cls = "fn"
            status_label = "Faux Négatif"
            status_class = "label-fn"
        
        prob_html = f"<div><strong>Probabilité :</strong> {s['prob']:.4f}</div>" if s['prob'] > 0 else ""
        gt_match_html = f"<div class='meta-info'><strong>Match Ground Truth :</strong><br>'{s['gt_match']}'<br>(Similitude: {s['sim']:.2f})</div>" if s['is_gt'] else ""

        html_content += f"""<span class="sentence {cls} tooltip">{s['text']} <span class="tooltiptext"><span class="{status_class}"><strong>{status_label}</strong></span>{prob_html}{gt_match_html}</span></span> """

    html_content += """
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="Visualise la détection des chroniques par rapport au ground truth.")
    parser.add_argument("transcription", help="Fichier transcription (.txt ou .srt)")
    parser.add_argument("ground_truth", help="Fichier ground truth (.txt)")
    parser.add_argument("--model", default="./camembert_chronicle_start_v3", help="Modèle à utiliser")
    parser.add_argument("--threshold", type=float, default=0.8, help="Seuil de confiance")
    parser.add_argument("--window_size", type=int, default=3, help="Taille de la fenêtre (nombre de phrases)")
    parser.add_argument("--live", action="store_true", help="Simuler une détection live (stricte)")
    parser.add_argument("--output", default="report.html", help="Nom du fichier de sortie")
    
    args = parser.parse_args()

    # Import dynamique pour éviter de charger torch si on n'en a pas besoin tout de suite
    import torch
    
    with open(args.transcription, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if args.transcription.lower().endswith(".srt"):
        print("Nettoyage du fichier SRT...")
        content = clean_srt_content(content)
        
    with open(args.ground_truth, 'r', encoding='utf-8') as f:
        gt_sentences = [line.strip() for line in f if line.strip()]

    if args.live:
        detector = LiveChronicleDetector(model_path=args.model, window_size=args.window_size, threshold=args.threshold)
    else:
        detector = ChronicleDetectorV2(model_path=args.model)

    sentences = detector.split_into_sentences(content)
    
    tp, fp, fn = 0, 0, 0
    similarity_threshold = 0.6

    print(f"Analyse de {len(sentences)} phrases...")
    
    all_probs = [0.0] * len(sentences)
    detected_indices = []

    if args.live:
        print("Mode LIVE activé")
        for i, sentence in enumerate(sentences):
            # En mode live, le détecteur gère son buffer et son état interne
            res = detector.process_new_sentence(sentence)
            if res:
                # Dans LiveChronicleDetector, l'index retourné est 1-based par rapport au début du flux
                # On le convertit en 0-based pour notre liste sentences
                detected_indices.append(res['index'] - 1)
                all_probs[res['index'] - 1] = res['confidence']
    else:
        print(f"Mode standard avec fenêtre de {args.window_size}...")
        # 1. Calcul des probabilités pour chaque segment (fenêtre)
        for i in range(len(sentences)):
            context = " ".join(sentences[i : i + args.window_size])
            inputs = detector.tokenizer(
                context, 
                return_tensors="pt", 
                truncation=True, 
                max_length=256
            ).to(detector.device)
            
            with torch.no_grad():
                outputs = detector.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                prob_start = probs[0][1].item()
                all_probs[i] = prob_start

        # 2. Application du post-processing
        for i, prob in enumerate(all_probs):
            if prob >= args.threshold:
                if not detected_indices or i > detected_indices[-1] + 5:
                    detected_indices.append(i)

    # 3. Construction des données pour le rapport et calcul des stats
    sentences_data = []
    matched_gt_indices = set()

    for i, sentence in enumerate(sentences):
        is_detected = i in detected_indices
        prob_start = all_probs[i]
        
        # Matching GT
        is_gt = False
        best_gt_match = ""
        best_sim = 0
        
        for gt_idx, gt in enumerate(gt_sentences):
            sim = string_similarity(sentence[:200], gt[:200])
            if sim > best_sim:
                best_sim = sim
                best_gt_match = gt
                current_gt_idx = gt_idx
        
        if best_sim >= similarity_threshold:
            is_gt = True
            matched_gt_indices.add(current_gt_idx)

        if is_detected and is_gt: tp += 1
        elif is_detected and not is_gt: fp += 1
        elif not is_detected and is_gt: fn += 1

        sentences_data.append({
            "text": sentence,
            "is_detected": is_detected,
            "prob": prob_start,
            "is_gt": is_gt,
            "gt_match": best_gt_match,
            "sim": best_sim
        })

    # Calcul des FN restants (ceux qui n'ont jamais été matchés)
    # Dans notre boucle ci-dessus, on compte les segments qui sont GT.
    # Mais un GT peut s'étendre sur plusieurs segments ou être manqué.
    # Pour simplifier le rapport visuel, on reste sur une base "par segment".
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    
    stats = {
        'tp': tp, 'fp': fp, 'fn': fn,
        'precision': precision, 'recall': recall
    }

    generate_html_report(sentences_data, args.output, os.path.basename(args.transcription), stats)
    print(f"\n✅ Rapport généré : {os.path.abspath(args.output)}")
    print(f"📊 TP: {tp} | FP: {fp} | FN: {fn}")
    print(f"🎯 Précision: {precision:.2f} | Rappel: {recall:.2f}")
    
    try:
        webbrowser.open('file://' + os.path.abspath(args.output))
    except:
        pass

if __name__ == "__main__":
    main()

