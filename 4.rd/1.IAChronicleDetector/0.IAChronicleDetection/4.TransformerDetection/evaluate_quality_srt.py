import os
import argparse
import torch
import pandas as pd
import numpy as np
import re
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from tqdm import tqdm
from difflib import SequenceMatcher
from src.utils import load_transcription, format_timecode

# --- Configuration par défaut ---
DEFAULT_MODEL = "models/camembert_chronicle"

def string_similarity(a, b):
    """Calcule la similitude entre deux chaînes (0.0 à 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def load_gt_sentences_from_srt(gt_srt_path):
    """
    Extrait les phrases de référence depuis un fichier SRT avec leurs timecodes.
    Chaque segment du SRT est considéré comme le début d'une chronique.
    """
    segments = load_transcription(gt_srt_path)
    return [{"sentence": seg['text'], "start_time": seg['start']} for seg in segments]

def split_into_sentences(text):
    """Découpe un texte en phrases basées sur la ponctuation."""
    # Remplacement de tous les types de sauts de ligne par des espaces
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    
    # Ajout d'espaces après la ponctuation si manquants (ex: "Bonjour.Comment" -> "Bonjour. Comment")
    text = re.sub(r'([.!?,:;])(?=[^\s\d])', r'\1 ', text)
    
    # Suppression des doubles espaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Découpage sur la ponctuation de fin de phrase
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]

def get_predicted_starts(model_path, srt_path, threshold=0.1, window_size=2):
    """
    Prédit les chroniques et renvoie le texte du premier segment de chaque chronique détectée.
    Supporte SRT (avec timecodes) et TXT (découpage par phrases).
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle non trouvé à {model_path}")
    
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
    model.to(device)
    model.eval()

    is_txt = srt_path.lower().endswith('.txt')
    
    if is_txt:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()
        sentences_text = split_into_sentences(raw_text)
        segments = [{'text': s, 'start': 0, 'end': 0} for s in sentences_text]
    else:
        segments = load_transcription(srt_path)
        
    if not segments:
        return []
        
    # Préparation des textes avec contexte
    texts = []
    for i in range(len(segments)):
        start_idx = max(0, i - window_size)
        end_idx = min(len(segments), i + window_size + 1)
        context_texts = [segments[j]['text'] for j in range(start_idx, end_idx)]
        texts.append(" [SEP] ".join(context_texts))
    
    # Inférence par lots
    batch_size = 16
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            encodings = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt"
            ).to(device)
            
            outputs = model(**encodings)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            all_probs.extend(probs[:, 1].cpu().numpy())

    # Seuil et Lissage
    raw_preds = (pd.Series(all_probs) > threshold).astype(int).values
    preds_smoothed = raw_preds.copy()
    for i in range(1, len(preds_smoothed) - 1):
        if preds_smoothed[i-1] == 1 and preds_smoothed[i+1] == 1:
            preds_smoothed[i] = 1
            
    # Grouper en intervalles et extraire le premier segment
    detected_starts = []
    current_ch_start_idx = None
    
    for i, pred in enumerate(preds_smoothed):
        if pred == 1:
            if current_ch_start_idx is None:
                current_ch_start_idx = i
        else:
            if current_ch_start_idx is not None:
                if is_txt:
                    detected_starts.append({
                        "sentence": segments[current_ch_start_idx]['text'],
                        "start_time": 0
                    })
                else:
                    duration = segments[i-1]['end'] - segments[current_ch_start_idx]['start']
                    if duration >= 30:
                        detected_starts.append({
                            "sentence": segments[current_ch_start_idx]['text'],
                            "start_time": segments[current_ch_start_idx]['start']
                        })
                current_ch_start_idx = None
                
    if current_ch_start_idx is not None:
        if is_txt:
            detected_starts.append({
                "sentence": segments[current_ch_start_idx]['text'],
                "start_time": 0
            })
        else:
            duration = segments[-1]['end'] - segments[current_ch_start_idx]['start']
            if duration >= 30:
                detected_starts.append({
                    "sentence": segments[current_ch_start_idx]['text'],
                    "start_time": segments[current_ch_start_idx]['start']
                })
            
    return detected_starts

def evaluate_on_srt(model_path, transcription_path, gt_srt, threshold=0.1):
    # 1. Chargement des données
    gt_data = load_gt_sentences_from_srt(gt_srt)
    if not gt_data:
        print("Erreur : Aucun point de référence trouvé dans le fichier SRT Ground Truth.")
        return
    gt_sentences = [res["sentence"] for res in gt_data]

    # 2. Prédiction
    predicted_starts = get_predicted_starts(model_path, transcription_path, threshold=threshold)
    predicted_sentences = [res["sentence"] for res in predicted_starts]

    # 3. Comparaison (Matching Textuel) pour le calcul du score
    tp = 0
    matched_gt_indices = set()
    matches = []
    similarity_threshold = 0.6

    for p_idx, p_sent in enumerate(predicted_sentences):
        best_sim = 0
        best_gt_idx = -1
        for g_idx, g_sent in enumerate(gt_sentences):
            if g_idx in matched_gt_indices: continue
            sim = string_similarity(p_sent[:150], g_sent[:150])
            if sim > best_sim:
                best_sim = sim
                best_gt_idx = g_idx
        
        if best_gt_idx != -1 and best_sim >= similarity_threshold:
            tp += 1
            matched_gt_indices.add(best_gt_idx)
            matches.append({"similarity": best_sim})

    # 4. Affichage simplifié
    print("\n--- INFÉRENCE DU MODÈLE (Détections) ---")
    if not predicted_starts:
        print("Aucune détection.")
    for res in predicted_starts:
        time_str = format_timecode(res['start_time']) if not transcription_path.lower().endswith('.txt') else "N/A"
        print(f"[{time_str}] {res['sentence'][:120]}...")

    print("\n--- GROUND TRUTH (Références) ---")
    for res in gt_data:
        time_str = format_timecode(res['start_time'])
        print(f"[{time_str}] {res['sentence'][:120]}...")

    # 5. Calcul des scores
    fp = len(predicted_sentences) - tp
    fn = len(gt_sentences) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    avg_similarity = sum(m["similarity"] for m in matches) / len(matches) if matches else 0.0

    # Note de Qualité (70% F1, 30% Fidélité Textuelle)
    card_score = f1 * 100
    text_score = avg_similarity * 100
    global_score = (card_score * 0.7) + (text_score * 0.3)

    print("\n" + "="*45)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*45)
    print(f"(F1: {f1:.2f}, Sim: {avg_similarity:.2f}, Détéctions: {len(predicted_sentences)}/{len(gt_sentences)})")
    print("="*45 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue la qualité du Transformer en utilisant un SRT comme ground truth.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Chemin vers le dossier du modèle entraîné (ex: models/camembert_chronicle).")
    parser.add_argument("--transcription", required=True, help="Chemin vers le fichier de transcription à analyser (.srt ou .txt).")
    parser.add_argument("--ground-truth", required=True, help="Chemin vers le fichier SRT de référence servant de vérité terrain.")
    parser.add_argument("--threshold", type=float, default=0.1, help="Seuil de confiance pour la détection (défaut: 0.1).")
    
    args = parser.parse_args()
    
    evaluate_on_srt(
        model_path=args.model, 
        transcription_path=args.transcription, 
        gt_srt=args.ground_truth,
        threshold=args.threshold
    )
