import os
import argparse
import torch
import numpy as np
import sys
import time
import json
import librosa
from transformers import (
    CamembertTokenizer, 
    CamembertForSequenceClassification, 
    KyutaiSpeechToTextProcessor, 
    KyutaiSpeechToTextForConditionalGeneration
)
from src.utils import load_transcription, load_timecodes
from src.evaluation import evaluate_chronicles

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def save_results_json(detected_chronicles, output_path):
    """Sauvegarde les résultats au format JSON demandé."""
    formatted_results = []
    for c in detected_chronicles:
        formatted_results.append({
            "label": "chronique",
            "start": round(c['start'], 2),
            "end": round(c['end'], 2),
            "detected_at": round(c['detected_at'], 2),
            "confidence": round(c['conf'], 3)
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(formatted_results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Résultats sauvegardés dans : {output_path}")

def evaluate_quality_live_kyutai(model_path, audio_path, tc_path=None, threshold=0.5, acceleration=None, output_json=None):
    """
    Évaluation avec transcription en live via Kyutai STT (inférence manuelle) et détection en live via Camembert.
    """
    if not os.path.exists(model_path):
        print(f"Erreur : Modèle chronicle non trouvé à {model_path}")
        return

    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Utilisation du device : {device}")

    # 1. Chargement de Kyutai STT
    print(f"Chargement du modèle Kyutai STT (kyutai/stt-1b-en_fr-trfs)...")
    try:
        stt_processor = KyutaiSpeechToTextProcessor.from_pretrained("kyutai/stt-1b-en_fr-trfs")
        stt_model = KyutaiSpeechToTextForConditionalGeneration.from_pretrained(
            "kyutai/stt-1b-en_fr-trfs",
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
        ).to(device)
    except Exception as e:
        print(f"Erreur lors du chargement de Kyutai STT : {e}")
        return

    # 2. Chargement du Classifier Chronicle (Camembert)
    print(f"Chargement du classifier Camembert depuis {model_path}...")
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    model.eval()
    model.to(device)

    # 3. Chargement et découpage de l'audio
    print(f"Chargement de l'audio : {audio_path} (resampling à 24kHz)...")
    audio, sr = librosa.load(audio_path, sr=24000)
    total_duration = len(audio) / sr
    
    # On utilise des chunks de 5 secondes pour simuler le live
    chunk_size_s = 5.0
    chunk_samples = int(chunk_size_s * sr)
    
    print(f"\n--- DÉBUT DÉTECTION LIVE (Kyutai STT + Camembert) ---")
    
    segments_history = []
    detected_chronicles = []
    current_chronicle = None
    window_size = 2
    
    start_wall_time = time.time()
    
    for i in range(0, len(audio), chunk_samples):
        chunk = audio[i : i + chunk_samples]
        s_start = i / sr
        s_end = min((i + chunk_samples) / sr, total_duration)

        # Simulation de l'écoulement du temps réel
        if acceleration and acceleration > 0:
            target_wall_time = s_end / acceleration
            elapsed = time.time() - start_wall_time
            if target_wall_time > elapsed:
                time.sleep(target_wall_time - elapsed)

        # Transcription du chunk
        inputs = stt_processor(chunk, sampling_rate=sr, return_tensors="pt").to(device)
        with torch.no_grad():
            output_tokens = stt_model.generate(**inputs, max_new_tokens=128)
        text = stt_processor.batch_decode(output_tokens, skip_special_tokens=True)[0].strip()
        
        if not text:
            # Même si pas de texte, on peut loguer le temps
            continue

        # Stockage du segment
        segments_history.append({'start': s_start, 'end': s_end, 'text': text})
        
        # Inférence Camembert (contexte passé uniquement)
        start_idx = max(0, len(segments_history) - 1 - window_size)
        context_str = " [SEP] ".join([segments_history[j]['text'] for j in range(start_idx, len(segments_history))])
        
        encodings = tokenizer(context_str, padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**encodings)
            prob = torch.softmax(outputs.logits, dim=1)[:, 1].item()

        # Logique de détection de segment de chronique
        if prob >= threshold:
            if current_chronicle is None:
                current_chronicle = {'start': s_start, 'end': s_end, 'conf': prob}
            else:
                current_chronicle['end'] = s_end
                current_chronicle['conf'] = max(current_chronicle['conf'], prob)
        else:
            if current_chronicle:
                if current_chronicle['end'] - current_chronicle['start'] >= 5.0:
                    current_chronicle['detected_at'] = s_end
                    detected_chronicles.append(current_chronicle)
                    print(f"✨ Chronique détectée ! [{current_chronicle['start']:.1f}s - {current_chronicle['end']:.1f}s] à {s_end:.1f}s")
                current_chronicle = None
        
        status = "🔴 [CHRONIQUE]" if prob >= threshold else "           "
        print(f"[{s_start:6.1f}s - {s_end:6.1f}s] {status} | Prob: {prob:.2f} | {text[:50]}...")

    if current_chronicle and current_chronicle['end'] - current_chronicle['start'] >= 5.0:
        current_chronicle['detected_at'] = total_duration
        detected_chronicles.append(current_chronicle)

    # Sauvegarde JSON
    if output_json:
        save_results_json(detected_chronicles, output_json)

    # 4. Évaluation si GT fourni
    if tc_path and os.path.exists(tc_path):
        ground_truth = load_timecodes(tc_path)
        print(f"\n🔍 Résultats vs Ground Truth ({len(ground_truth)} attendues) :")
        for i, gt in enumerate(ground_truth, 1):
            best_iou = 0
            for p in detected_chronicles:
                iou = calculate_iou((p['start'], p['end']), gt)
                best_iou = max(best_iou, iou)
            res = "OK" if best_iou > 0.1 else "MISS"
            print(f"  Chronique GT {i} ({gt[0]:.1f}s) : {res} (Max IOU: {best_iou:.2f})")

        metrics = evaluate_chronicles(detected_chronicles, ground_truth)
        final_score = (metrics['cardinality_score']*0.4 + metrics['alignment_score']*0.6)*100
        print(f"\n📊 NOTE FINALE QUALITÉ : {final_score:.1f}/100")

def evaluate_quality_whisper(model_path, audio_path, tc_path=None, live_sim=True, acceleration=None, output_json=None):
    """Ancienne méthode Whisper."""
    from detect import transcribe_audio, predict_chroniques
    print(f"Transcription complète avec Whisper...")
    segments = transcribe_audio(audio_path)
    
    if live_sim:
        tokenizer = CamembertTokenizer.from_pretrained(model_path)
        model = CamembertForSequenceClassification.from_pretrained(model_path)
        model.eval()
        device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
        model.to(device)
        
        all_probs = []
        window_size = 2
        for i in range(len(segments)):
            start_idx = max(0, i - window_size)
            context_str = " [SEP] ".join([segments[j]['text'] for j in range(start_idx, i + 1)])
            encodings = tokenizer(context_str, padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
            with torch.no_grad():
                outputs = model(**encodings)
                all_probs.append(torch.softmax(outputs.logits, dim=1)[:, 1].item())
        
        predicted_chronicles = []
        current = None
        for i, p in enumerate(all_probs):
            if p >= 0.5:
                if current is None: current = {'start': segments[i]['start'], 'end': segments[i]['end'], 'conf': p}
                else: current['end'] = segments[i]['end']; current['conf'] = max(current['conf'], p)
            else:
                if current:
                    if current['end'] - current['start'] >= 5.0:
                        current['detected_at'] = segments[i]['end']
                        predicted_chronicles.append(current)
                    current = None
        if current:
            current['detected_at'] = segments[-1]['end']
            predicted_chronicles.append(current)
    else:
        predicted_chronicles = predict_chroniques(model_path, segments)
        for p in predicted_chronicles:
            p['detected_at'] = p['end']
            p['conf'] = p.get('confidence', 0.5)

    if output_json:
        save_results_json(predicted_chronicles, output_json)

    if tc_path and os.path.exists(tc_path):
        ground_truth = load_timecodes(tc_path)
        metrics = evaluate_chronicles(predicted_chronicles, ground_truth)
        final_score = (metrics['cardinality_score']*0.4 + metrics['alignment_score']*0.6)*100
        print(f"\n📊 NOTE FINALE QUALITÉ (Whisper) : {final_score:.1f}/100")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Détection de chroniques en live")
    parser.add_argument("--model", default="models/camembert_chronicle")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--gt", default=None)
    parser.add_argument("--kyutai", action="store_true")
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--acceleration", type=float, default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", default="results_detection.json")
    args = parser.parse_args()
    
    if args.kyutai:
        evaluate_quality_live_kyutai(args.model, args.audio, args.gt, threshold=args.threshold, acceleration=args.acceleration, output_json=args.output)
    else:
        evaluate_quality_whisper(args.model, args.audio, args.gt, live_sim=not args.no_live, acceleration=args.acceleration, output_json=args.output)
