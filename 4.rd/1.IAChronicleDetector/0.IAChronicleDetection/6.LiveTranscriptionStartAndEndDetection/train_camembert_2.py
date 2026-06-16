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
from huggingface_hub import add_collection_item
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# --- Configuration ---
MODEL_NAME = "camembert-base"
DATA_PATH = "../../../@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
OUTPUT_DIR = "./camembert_chronicle_start_v2"
WANDB_PROJECT = "IAChronicleDetection"
HF_REPO_NAME = "eglantinefonrose/camembert-chronicle-start-detection-v2"
HF_COLLECTION_SLUG = "eglantinefonrose/rlac-radio-live-a-la-carte-69dbc4adbaf921268f565853"

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

def load_data_with_augmentation():
    """
    Charge les données avec augmentation :
    - Positifs : 1, 2 et 3 premières phrases (3 exemples par fichier)
    - Négatifs : Fins de chroniques ET extraits du milieu (neutres)
    """
    data = []
    
    # 1. POSITIFS (Débuts)
    start_dirs = glob.glob(os.path.join(DATA_PATH, "**/start_transcription"), recursive=True)
    print(f"Dossiers de début trouvés : {len(start_dirs)}")
    
    for d in start_dirs:
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"):
                        content = clean_srt_content(content)
                    
                    sentences = get_sentences(content)
                    if not sentences:
                        continue
                        
                    # Augmentation : on prend 1, 2 et 3 phrases
                    # Cela permet au modèle d'apprendre le "Bonjour" seul,
                    # mais aussi le "Bonjour, aujourd'hui on parle de..."
                    for i in range(1, min(4, len(sentences) + 1)):
                        context = " ".join(sentences[:i])
                        data.append({"text": context, "label": 1})
            except Exception as e:
                print(f"Erreur lecture {f}: {e}")

    num_pos = len([d for d in data if d["label"] == 1])
    print(f"Échantillons positifs après augmentation : {num_pos}")

    # 2. NÉGATIFS (Fins)
    end_dirs = glob.glob(os.path.join(DATA_PATH, "**/end_transcription"), recursive=True)
    print(f"Dossiers de fin trouvés : {len(end_dirs)}")
    
    for d in end_dirs:
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"):
                        content = clean_srt_content(content)
                    
                    sentences = get_sentences(content)
                    if not sentences:
                        continue
                    
                    # On prend la fin (3 phrases)
                    context = " ".join(sentences[-3:])
                    data.append({"text": context, "label": 0})
            except Exception as e:
                print(f"Erreur lecture {f}: {e}")

    # 3. NÉGATIFS (Neutres / Milieu)
    # On va chercher des fichiers qui ne sont pas dans start/end pour varier
    # Ici, on prend simplement le milieu des fichiers de fin pour simplifier l'accès
    for d in end_dirs:
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    sentences = get_sentences(content)
                    if len(sentences) > 6:
                        # On prend un bloc au milieu
                        mid = len(sentences) // 2
                        context = " ".join(sentences[mid:mid+3])
                        data.append({"text": context, "label": 0})
            except:
                pass
                
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
    # 1. Chargement et Augmentation
    print("Chargement et augmentation des données...")
    df = load_data_with_augmentation()
    
    # Équilibrage simple : on s'assure de ne pas avoir 10x plus de négatifs
    pos_df = df[df['label'] == 1]
    neg_df = df[df['label'] == 0]
    
    if len(neg_df) > len(pos_df) * 2:
        neg_df = neg_df.sample(len(pos_df) * 2, random_state=42)
    
    df = pd.concat([pos_df, neg_df]).sample(frac=1, random_state=42).reset_index(drop=True)
    
    print(f"Total d'échantillons final : {len(df)}")
    print(df['label'].value_counts())

    # 2. Split
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        df['text'].tolist(), 
        df['label'].tolist(), 
        test_size=0.15, # Un peu moins de val car peu de données
        random_state=42, 
        stratify=df['label'].tolist()
    )

    # 3. Tokenization
    tokenizer = CamembertTokenizer.from_pretrained(MODEL_NAME)
    train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=256) # Max length augmenté
    val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=256)

    train_dataset = ChronicleDataset(train_encodings, train_labels)
    val_dataset = ChronicleDataset(val_encodings, val_labels)

    # 4. Modèle
    model = CamembertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    # 5. WandB
    wandb.init(project=WANDB_PROJECT, name=f"camembert-chronicle-v2-{pd.Timestamp.now().strftime('%m%d-%H%M')}")

    # 6. Training Arguments (Optimisés)
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=10,             # Plus d'époques pour un petit dataset
        per_device_train_batch_size=8,   # Batch size plus petit pour mieux généraliser
        per_device_eval_batch_size=8,
        learning_rate=2e-5,              # LR plus bas
        warmup_ratio=0.1,                # Warmup basé sur le ratio plutôt que steps fixes
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",      # F1 est plus important que l'accuracy ici
        report_to="wandb",
        push_to_hub=True,
        hub_model_id=HF_REPO_NAME,
    )

    # 7. Trainer avec Early Stopping
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)] # Arrêt si pas d'amélioration après 3 époques
    )

    print("Début de l'entrainement V2...")
    trainer.train()
    
    # 8. Sauvegarde et Evaluation
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    eval_results = trainer.evaluate()
    print(f"\nRésultats finaux : {eval_results}")
    
    # Publication
    trainer.push_to_hub()
    wandb.finish()

if __name__ == "__main__":
    train()
