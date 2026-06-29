import os
import glob
import torch
import pandas as pd
import numpy as np
import re
import argparse
from transformers import CamembertTokenizer, CamembertForSequenceClassification, Trainer, TrainingArguments
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from inference import ChronicleDetector
from difflib import SequenceMatcher

# --- Configuration par défaut ---
DATA_PATH = "../../../@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
DEFAULT_MODEL = "./camembert_chronicle_start"

class ChronicleDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='binary')
    acc = accuracy_score(labels, preds)
    return {
        'accuracy': acc,
        'f1': f1,
        'precision': precision,
        'recall': recall
    }

def clean_srt_content(content):
    """Supprime les indices et les horodatages des fichiers SRT."""
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if '-->' in line:
            continue
        clean_lines.append(line)
    return " ".join(clean_lines)

def load_evaluation_data(data_path):
    """Charge les données depuis les dossiers start/end pour l'évaluation."""
    data = []
    # Positifs
    start_dirs = glob.glob(os.path.join(data_path, "**/start_transcription"), recursive=True)
    for d in start_dirs:
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"):
                        content = clean_srt_content(content)
                    content = content.replace('\n', ' ').strip()
                    if content: data.append({"text": content[:200], "label": 1})
            except: pass

    # Négatifs
    end_dirs = glob.glob(os.path.join(data_path, "**/end_transcription"), recursive=True)
    for d in end_dirs:
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"):
                        content = clean_srt_content(content)
                    content = content.replace('\n', ' ').strip()
                    if content: data.append({"text": content[:200], "label": 0})
            except: pass
                
    return pd.DataFrame(data)

def parse_gt_sentences(file_path):
    """
    Lit le fichier des premières phrases des chroniques (une par ligne).
    """
    sentences = []
    if not file_path or not os.path.exists(file_path):
        return sentences
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s:
                sentences.append(s)
    return sentences

def string_similarity(a, b):
    """Calcule la similitude entre deux chaînes (0.0 à 1.0)."""
    return SequenceMatcher(None, a, b).ratio()

def evaluate_on_file(model_path, transcription_path, gt_sentences_path, threshold=0.85):
    print(f"--- Évaluation sur fichier (Textuelle) ---")
    print(f"Modèle : {model_path}")
    print(f"Transcription : {transcription_path}")
    print(f"Sentences (GT) : {gt_sentences_path}")

    # 1. Chargement du modèle
    detector = ChronicleDetector(model_path=model_path)

    # 2. Préparation des données
    with open(transcription_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    gt_sentences = parse_gt_sentences(gt_sentences_path)
    if not gt_sentences:
        print("Erreur : Aucun point de référence (sentences) trouvé.")
        return
    print(f"Chargement de {len(gt_sentences)} phrases ground truth.")

    # 3. Détection des débuts dans la transcription
    print(f"Analyse du texte...")
    detected_results = detector.predict_starts(raw_text, threshold=threshold, group_consecutive=True)
    predicted_sentences = [res["sentence"] for res in detected_results]
    
    print(f"Phrases détectées : {len(predicted_sentences)}")
    if predicted_sentences:
        print("\n--- Liste des phrases détectées ---")
        for i, s in enumerate(predicted_sentences, 1):
            print(f"  {i}. {s[:120]}...")

    # 4. Comparaison (Matching Textuel)
    tp = 0
    matched_gt_indices = set()
    matches = []
    similarity_threshold = 0.6 # Seuil pour considérer que c'est la même phrase (STT peut varier)

    print("\n--- Détail des Comparaisons ---")
    for p_idx, p_sent in enumerate(predicted_sentences):
        best_sim = 0
        best_gt_idx = -1
        
        for g_idx, g_sent in enumerate(gt_sentences):
            if g_idx in matched_gt_indices:
                continue
            
            sim = string_similarity(p_sent[:150].lower(), g_sent[:150].lower())
            if sim > best_sim:
                best_sim = sim
                best_gt_idx = g_idx
        
        print(f"\n[Détection {p_idx+1}]")
        print(f"  Modèle : {p_sent[:100]}...")
        
        if best_gt_idx != -1 and best_sim >= similarity_threshold:
            tp += 1
            matched_gt_indices.add(best_gt_idx)
            matches.append({
                "pred": p_sent,
                "gt": gt_sentences[best_gt_idx],
                "similarity": best_sim
            })
            is_exact = "IDENTIQUE" if best_sim > 0.98 else f"SIMILAIRE ({best_sim:.2f})"
            print(f"  GT     : {gt_sentences[best_gt_idx][:100]}...")
            print(f"  Statut : ✅ {is_exact}")
        else:
            print(f"  Statut : ❌ AUCUN MATCH (Meilleure sim: {best_sim:.2f})")
            if best_gt_idx != -1:
                print(f"  Proche : {gt_sentences[best_gt_idx][:100]}...")
    
    # Phrases GT non trouvées
    missing_gt = [s for i, s in enumerate(gt_sentences) if i not in matched_gt_indices]
    if missing_gt:
        print("\n--- Phrases Ground Truth non détectées (Oublis) ---")
        for s in missing_gt:
            print(f"  - {s[:100]}...")

    fp = len(predicted_sentences) - tp
    fn = len(gt_sentences) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    avg_similarity = sum(m["similarity"] for m in matches) / len(matches) if matches else 0.0

    # 5. Calcul de la Note de Qualité
    card_score = f1 * 100
    text_score = avg_similarity * 100
    global_score = (card_score * 0.7) + (text_score * 0.3)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- Cardinalité (F1) (70%) : {card_score:.1f}%")
    print(f"- Fidélité Textuelle (30%) : {text_score:.1f}%")
    print("-" * 40)
    print(f"Détails : TP={tp}, FP={fp}, FN={fn}")
    print(f"Précision={precision:.4f}, Rappel={recall:.4f}, F1={f1:.4f}")
    print(f"Similitude moyenne des matches : {avg_similarity:.2f}")
    print("="*40)

def evaluate(model_path, data_path):
    print(f"--- Évaluation du modèle (Dataset) : {model_path} ---")
    
    # 1. Chargement du modèle et tokenizer
    tokenizer = CamembertTokenizer.from_pretrained(model_path)
    model = CamembertForSequenceClassification.from_pretrained(model_path)
    
    # 2. Chargement des données
    df = load_evaluation_data(data_path)
    if df.empty:
        print("Erreur : Aucune donnée trouvée pour l'évaluation.")
        return

    print(f"Données chargées : {len(df)} échantillons.")

    # 3. Préparation du dataset
    encodings = tokenizer(df['text'].tolist(), truncation=True, padding=True, max_length=128)
    dataset = ChronicleDataset(encodings, df['label'].tolist())

    # 4. Trainer pour l'évaluation
    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir="./tmp_eval", per_device_eval_batch_size=16, report_to="none"),
        compute_metrics=compute_metrics
    )

    # 5. Calcul des métriques
    results = trainer.evaluate(eval_dataset=dataset)
    
    # 6. Calcul de la Note de Qualité
    card_score = results.get('eval_f1', 0) * 100
    acc_score = results.get('eval_accuracy', 0) * 100
    global_score = (card_score * 0.7) + (acc_score * 0.3)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score:.1f}/100")
    print("="*40)
    print(f"- Cardinalité (F1) (70%) : {card_score:.1f}%")
    print(f"- Précision (Acc) (30%) : {acc_score:.1f}%")
    print("-" * 40)
    print(f"Détails : F1={results['eval_f1']:.4f}, Acc={results['eval_accuracy']:.4f}")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue un modèle CamemBERT existant sur un dataset ou un fichier spécifique.")
    parser.add_argument("model_path", help="Chemin vers le modèle.")
    parser.add_argument("--data", default=DATA_PATH, help="Chemin vers le dossier assets (pour le mode dataset).")
    parser.add_argument("--transcription", help="Chemin vers le fichier de transcription (.txt).")
    parser.add_argument("--sentences", help="Chemin vers le fichier contenant les premières phrases des chroniques (ground truth).")
    parser.add_argument("--threshold", type=float, default=0.85, help="Seuil de confiance pour la détection (défaut: 0.85).")
    
    args = parser.parse_args()
    
    if args.transcription and args.sentences:
        evaluate_on_file(
            args.model_path, 
            args.transcription, 
            gt_sentences_path=args.sentences,
            threshold=args.threshold
        )
    else:
        evaluate(args.model_path, args.data)
