import os
import glob
import torch
import pandas as pd
import numpy as np
import re
import wandb
from transformers import (
    CamembertTokenizer, 
    CamembertForSequenceClassification, 
    Trainer, 
    TrainingArguments,
    EarlyStoppingCallback
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# --- Configuration ---
MODEL_NAME = "./camembert_chronicle_start_v3" # On repart de la V3
DATA_PATH = "../../../@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
OUTPUT_DIR = "./camembert_chronicle_start_v4"
WANDB_PROJECT = "IAChronicleDetection"
HF_REPO_NAME = "eglantinefonrose/camembert-chronicle-start-detection-v4"
WINDOW_SIZE = 3

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

def get_sentences(text):
    """Découpe proprement le texte en phrases."""
    if not text:
        return []
    text = text.replace('\n', ' ').strip()
    # Découpage sur . ! ou ? suivi d'un espace
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]

def load_data_v4():
    """
    Charge les données en incluant la transcription complète comme négatifs.
    """
    data = []
    
    # On cherche les répertoires d'épisodes (ex: franceinter-matin/05-01-2026)
    episode_dirs = glob.glob(os.path.join(DATA_PATH, "*/*"), recursive=False)
    print(f"Nombre d'épisodes trouvés : {len(episode_dirs)}")

    for ep_dir in episode_dirs:
        ep_id = os.path.basename(os.path.dirname(ep_dir)) + "_" + os.path.basename(ep_dir)
        chroniques_path = os.path.join(ep_dir, "chroniques")
        
        if not os.path.exists(chroniques_path):
            continue
            
        start_dir = os.path.join(chroniques_path, "start_transcription")
        end_dir = os.path.join(chroniques_path, "end_transcription")
        
        if not os.path.exists(start_dir) or not os.path.exists(end_dir):
            continue

        # Liste des chroniques dans cet épisode
        start_files = glob.glob(os.path.join(start_dir, "*.txt")) + glob.glob(os.path.join(start_dir, "*.srt"))
        start_files.sort()
        
        chronicle_sentences = {}
        positive_texts = set()

        for f in start_files:
            name = os.path.basename(f).replace("_start.txt", "").replace("_start.srt", "")
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"): content = clean_srt_content(content)
                    chronicle_sentences[name] = {"start": get_sentences(content)}
                
                # Chercher le fichier de fin correspondant
                f_end = f.replace("start_transcription", "end_transcription").replace("_start", "_end")
                if os.path.exists(f_end):
                    with open(f_end, 'r', encoding='utf-8') as file:
                        content = file.read()
                        if f_end.endswith(".srt"): content = clean_srt_content(content)
                        chronicle_sentences[name]["end"] = get_sentences(content)
            except Exception as e:
                print(f"Erreur lecture {f}: {e}")

        # 1. POSITIFS & TRANSITIONS
        names = list(chronicle_sentences.keys())
        for i, name in enumerate(names):
            starts = chronicle_sentences[name].get("start", [])
            if len(starts) < WINDOW_SIZE: continue
            
            # Transition depuis la chronique précédente
            if i > 0:
                prev_name = names[i-1]
                prev_ends = chronicle_sentences[prev_name].get("end", [])
                
                if len(prev_ends) >= 2:
                    # [fin-1, fin, debut]
                    context = " ".join([prev_ends[-2], prev_ends[-1], starts[0]])
                    data.append({"text": context, "label": 1, "group": ep_id})
                    positive_texts.add(context)
                    
                    # [fin, debut, debut+1]
                    context = " ".join([prev_ends[-1], starts[0], starts[1]])
                    data.append({"text": context, "label": 1, "group": ep_id})
                    positive_texts.add(context)

            # Fenêtre "propre" au début : [debut, debut+1, debut+2]
            context = " ".join(starts[:WINDOW_SIZE])
            data.append({"text": context, "label": 1, "group": ep_id})
            positive_texts.add(context)

        # 2. NÉGATIFS (Transcriptions complètes)
        full_trans_path = os.path.join(ep_dir, "full_show_transcription.txt")
        if os.path.exists(full_trans_path):
            try:
                with open(full_trans_path, 'r', encoding='utf-8') as f:
                    full_content = f.read()
                full_sentences = get_sentences(full_content)
                
                episode_negatives = []
                for i in range(len(full_sentences) - WINDOW_SIZE + 1):
                    window = full_sentences[i : i + WINDOW_SIZE]
                    context = " ".join(window)
                    
                    # On évite d'ajouter un positif comme négatif
                    # On fait un check simple : si le texte est dans positive_texts
                    if context in positive_texts:
                        continue
                    
                    # On peut aussi exclure si la 1ère ou 2ème phrase du window 
                    # est la 1ère phrase d'un début de chronique (pour être plus robuste)
                    is_too_close = False
                    for name in names:
                        ch_starts = chronicle_sentences[name].get("start", [])
                        if ch_starts and ch_starts[0] in window:
                            is_too_close = True
                            break
                    
                    if not is_too_close:
                        episode_negatives.append({"text": context, "label": 0, "group": ep_id})
                
                # On ajoute les négatifs de cet épisode (on pourra échantillonner plus tard)
                data.extend(episode_negatives)
                print(f"Episode {ep_id}: {len(episode_negatives)} négatifs ajoutés depuis la transcription complète.")
            except Exception as e:
                print(f"Erreur lors de la lecture de la transcription complète pour {ep_id}: {e}")
        else:
            # Fallback sur les négatifs "classiques" si pas de transcription complète
            for name in names:
                ends = chronicle_sentences[name].get("end", [])
                starts = chronicle_sentences[name].get("start", [])
                if len(ends) >= WINDOW_SIZE:
                    context = " ".join(ends[-WINDOW_SIZE:])
                    data.append({"text": context, "label": 0, "group": ep_id})
                if len(starts) > 10:
                    mid = len(starts) // 2
                    context = " ".join(starts[mid : mid + WINDOW_SIZE])
                    data.append({"text": context, "label": 0, "group": ep_id})

    return pd.DataFrame(data)

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

def train():
    print("Chargement des données V4 (Transcription complète comme négatifs)...")
    df = load_data_v4()
    
    print(f"Distribution initiale :\n{df['label'].value_counts()}")

    # Équilibrage : on garde un ratio raisonnable de négatifs
    pos_df = df[df['label'] == 1]
    neg_df = df[df['label'] == 0]
    
    # On prend jusqu'à 3 fois plus de négatifs que de positifs pour avoir un challenge réaliste 
    # mais sans noyer les positifs.
    max_neg = int(len(pos_df) * 3)
    if len(neg_df) > max_neg:
        neg_df = neg_df.sample(max_neg, random_state=42)
    
    df = pd.concat([pos_df, neg_df]).sample(frac=1, random_state=42).reset_index(drop=True)
    print(f"Distribution après équilibrage :\n{df['label'].value_counts()}")

    # Split par Groupe (Épisode) pour éviter le leakage
    gss = GroupShuffleSplit(n_splits=1, train_size=0.8, random_state=42)
    train_idx, val_idx = next(gss.split(df['text'], df['label'], groups=df['group']))
    
    train_df = df.iloc[train_idx]
    val_df = df.iloc[val_idx]

    print(f"Taille Train: {len(train_df)}, Taille Val: {len(val_df)}")
    print(f"Groupes en Train: {train_df['group'].nunique()}, Groupes en Val: {val_df['group'].nunique()}")

    # Tokenization
    tokenizer = CamembertTokenizer.from_pretrained(MODEL_NAME)
    train_encodings = tokenizer(train_df['text'].tolist(), truncation=True, padding=True, max_length=256)
    val_encodings = tokenizer(val_df['text'].tolist(), truncation=True, padding=True, max_length=256)

    train_dataset = ChronicleDataset(train_encodings, train_df['label'].tolist())
    val_dataset = ChronicleDataset(val_encodings, val_df['label'].tolist())

    # Modèle
    model = CamembertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    # WandB
    wandb.init(
        project=WANDB_PROJECT, 
        name=f"camembert-chronicle-v4-{pd.Timestamp.now().strftime('%m%d-%H%M')}",
        settings=wandb.Settings(init_timeout=300)
    )

    # Training Arguments
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        learning_rate=1e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to="wandb",
        push_to_hub=True,
        hub_model_id=HF_REPO_NAME,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
    )

    print("Début de l'entrainement V4...")
    trainer.train()
    
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    eval_results = trainer.evaluate()
    print(f"\nRésultats finaux : {eval_results}")
    
    trainer.push_to_hub()
    wandb.finish()

if __name__ == "__main__":
    train()
