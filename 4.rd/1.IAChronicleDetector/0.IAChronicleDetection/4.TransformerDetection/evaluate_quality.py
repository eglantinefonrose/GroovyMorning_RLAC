import os
import argparse
import torch
import numpy as np
import sys
import time
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from src.utils import load_transcription, load_timecodes
from src.evaluation import evaluate_chronicles

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def simulate_live_inference(model_path, srt_path, threshold=0.5, acceleration=None):
    """
    Simule une détection en direct avec Transformer.
    """
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
    model.to(device)

    segments = load_transcription(srt_path)
    print(f"Simulation live sur {len(segments)} segments...")
    if acceleration:
        print(f"Accélération : {acceleration}x")
        start_wall_time = time.time()
    
    all_probs = []
    window_size = 2 # Context passé uniquement pour le live
    
    with torch.no_grad():
        for i in range(len(segments)):
            if acceleration and acceleration > 0:
                T = segments[i]['start']
                target_wall_time = T / acceleration
                elapsed = time.time() - start_wall_time
                if target_wall_time > elapsed:
                    time.sleep(target_wall_time - elapsed)

            # En live strict, on n'a que le passé
            start_idx = max(0, i - window_size)
            context_texts = [segments[j]['text'] for j in range(start_idx, i + 1)]
            context_str = " [SEP] ".join(context_texts)
            
            encodings = tokenizer(
                context_str,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt"
            ).to(device)
            
            outputs = model(**encodings)
            prob = torch.softmax(outputs.logits, dim=1)[:, 1].item()
            all_probs.append(prob)

    detected_chronicles = []
    current = None
    for i, p in enumerate(all_probs):
        if p >= threshold:
            if current is None:
                current = {'start': segments[i]['start'], 'end': segments[i]['end'], 'conf': p}
            else:
                current['end'] = segments[i]['end']
                current['conf'] = max(current['conf'], p)
        else:
            if current:
                if current['end'] - current['start'] >= 5.0:
                    detected_chronicles.append(current)
                current = None
                
    if current and current['end'] - current['start'] >= 5.0:
        detected_chronicles.append(current)
        
    return detected_chronicles

def evaluate_quality(model_path, audio_path, tc_path, live_sim=True, acceleration=None):
    if not os.path.exists(model_path):
        print(f"Erreur : Modèle non trouvé.")
        return

    # For this script, audio_path seems to be used as srt_path in evaluate_quality context if passed as --audio
    # but transcribe_audio is called.
    from detect import transcribe_audio
    print(f"Transcription de {audio_path}...")
    segments = transcribe_audio(audio_path)

    mode_str = "LIVE SIMULÉ" if live_sim else "BATCH"
    print(f"--- Évaluation de Qualité ({mode_str}) pour Transformer ---")
    
    if live_sim:
        # Instead of calling predict_chroniques which might not have acceleration,
        # we can use our simulate_live_inference or implement it here.
        # But wait, predict_chroniques is what was there.
        # Let's use our simulate_live_inference if we want to support acceleration.
        predicted_chronicles = simulate_live_inference(model_path, audio_path, acceleration=acceleration)
    else:
        from detect import predict_chroniques
        predicted_chronicles = predict_chroniques(model_path, segments)

    # 3. Calculer les métriques
    ground_truth = load_timecodes(tc_path)
    print(f"\n🔍 Comparaison détaillée :")
    pred_used = set()
    for i, gt in enumerate(ground_truth, 1):
        best_iou = 0
        best_p = None
        for p in predicted_chronicles:
            iou = calculate_iou((p['start'], p['end']), gt)
            if iou > best_iou:
                best_iou = iou
                best_p = p

        if best_p:
            latency = max(0, best_p['start'] - gt[0])
            print(f"GT {i}: {gt[0]:.1f}s -> OK (Latence: {latency:.1f}s)")
        else:
            print(f"GT {i}: {gt[0]:.1f}s -> MISS")

    metrics = evaluate_chronicles(predicted_chronicles, ground_truth)
    print(f"\n📊 NOTE FINALE : {(metrics['cardinality_score']*0.4 + metrics['alignment_score']*0.6)*100:.1f}/100")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/camembert_chronicle")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", required=True)
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--acceleration", type=float, default=None, help="Acceleration factor for live simulation")
    args = parser.parse_args()
    evaluate_quality(args.model, args.audio, args.gt, live_sim=not args.no_live, acceleration=args.acceleration)
