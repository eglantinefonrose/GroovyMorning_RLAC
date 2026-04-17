import os
import torch
import pandas as pd
import argparse
from src.utils import load_transcription, format_timecode
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from tqdm import tqdm

MODEL_PATH = "models/camembert_chronicle"

def predict(srt_path: str):
    if not os.path.exists(MODEL_PATH):
        print(f"Erreur : Modèle non trouvé à {MODEL_PATH}. Lancez 'train.py' d'abord.")
        return
    
    print(f"Chargement du modèle Transformer depuis {MODEL_PATH}...")
    tokenizer = CamembertTokenizer.from_pretrained(MODEL_PATH)
    model = CamembertForSequenceClassification.from_pretrained(MODEL_PATH)
    model.eval() # Mode inférence
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    segments = load_transcription(srt_path)
    if not segments:
        print(f"Aucun segment trouvé dans {srt_path}")
        return
        
    print(f"Analyse de {len(segments)} segments avec le Transformer...")
    
    # Préparation des textes avec contexte (fenêtre de 2 comme dans l'entraînement)
    texts = []
    window_size = 2
    for i in range(len(segments)):
        start_idx = max(0, i - window_size)
        end_idx = min(len(segments), i + window_size + 1)
        context_texts = [segments[j]['text'] for j in range(start_idx, end_idx)]
        texts.append(" [SEP] ".join(context_texts))
    
    # Inférence par lots (batches) pour plus de rapidité
    batch_size = 16
    all_probs = []
    
    with torch.no_grad():
        for i in tqdm(range(0, len(texts), batch_size), desc="Prédiction"):
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
            all_probs.extend(probs[:, 1].cpu().numpy()) # Probabilité de la classe "Chronique"

    # Seuil de détection (0.5)
    raw_preds = (pd.Series(all_probs) > 0.1).astype(int).values
    
    # --- LISSAGE ---
    preds_smoothed = raw_preds.copy()
    # Combler les trous de 1 segment
    for i in range(1, len(preds_smoothed) - 1):
        if preds_smoothed[i-1] == 1 and preds_smoothed[i+1] == 1:
            preds_smoothed[i] = 1
            
    # Grouper en intervalles
    chronicles = []
    current_ch = None
    for i, pred in enumerate(preds_smoothed):
        if pred == 1:
            if current_ch is None:
                current_ch = {'start': segments[i]['start'], 'end': segments[i]['end']}
            else:
                current_ch['end'] = segments[i]['end']
        else:
            if current_ch is not None:
                # On ne garde que les chroniques de plus de 30 secondes
                if (current_ch['end'] - current_ch['start']) >= 30:
                    chronicles.append(current_ch)
                current_ch = None
    if current_ch and (current_ch['end'] - current_ch['start']) >= 30:
        chronicles.append(current_ch)
            
    print("\n--- Chroniques détectées (Transformer) ---")
    if not chronicles:
        print("Aucune chronique détectée dans cette émission.")
    else:
        for ch in chronicles:
            print(f"[{format_timecode(ch['start'])}] - [{format_timecode(ch['end'])}]")
    
    return chronicles

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srt_path")
    args = parser.parse_args()
    predict(args.srt_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("srt_path")
    args = parser.parse_args()
    predict(args.srt_path)
