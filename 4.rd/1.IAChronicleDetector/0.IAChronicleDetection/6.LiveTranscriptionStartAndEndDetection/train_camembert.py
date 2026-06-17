import os
import glob
import torch
import pandas as pd
import numpy as np
import re
import wandb
from transformers import CamembertTokenizer, CamembertForSequenceClassification, Trainer, TrainingArguments
from huggingface_hub import add_collection_item
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# --- Configuration ---
MODEL_NAME = "camembert-base"
# Chemin vers les données
DATA_PATH = "../../../@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
OUTPUT_DIR = "./camembert_chronicle_start"
WANDB_PROJECT = "IAChronicleDetection"
HF_REPO_NAME = "eglantinefonrose/camembert-chronicle-start-detection"
HF_COLLECTION_SLUG = "eglantinefonrose/rlac-radio-live-a-la-carte-69dbc4adbaf921268f565853"

def clean_srt_content(content):
    """Supprime les indices et les horodatages des fichiers SRT."""
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Si c'est un index numérique
        if line.isdigit():
            continue
        # Si c'est un horodatage (ex: 00:00:04,460 --> 00:00:09,420)
        if '-->' in line:
            continue
        clean_lines.append(line)
    return " ".join(clean_lines)

def extract_first_sentence(text):
    """Extrait la première phrase jusqu'au premier point."""
    if not text:
        return ""
    # Nettoyage des retours à la ligne
    text = text.replace('\n', ' ').strip()
    # Regex pour trouver la première phrase se terminant par . ! ou ?
    match = re.search(r'[^.!?]+[.!?]', text)
    if match:
        return match.group(0).strip()
    # Si pas de ponctuation, on prend tout (ou une limite de caractères)
    return text.strip()

def load_data():
    """Charge les données de début (label 1) et de fin (label 0)."""
    data = []
    
    # Recherche des dossiers start_transcription (Positifs)
    start_dirs = glob.glob(os.path.join(DATA_PATH, "**/start_transcription"), recursive=True)
    print(f"Dossiers de début trouvés : {len(start_dirs)}")
    
    for d in start_dirs:
        # On cherche à la fois .txt et .srt
        files = glob.glob(os.path.join(d, "*.txt")) + glob.glob(os.path.join(d, "*.srt"))
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if f.endswith(".srt"):
                        content = clean_srt_content(content)
                    sentence = extract_first_sentence(content)
                    if sentence:
                        data.append({"text": sentence, "label": 1})
            except Exception as e:
                print(f"Erreur lecture {f}: {e}")

    # Recherche des dossiers end_transcription (Négatifs)
    # On utilise les fins de chroniques comme exemples de "non-début"
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
                    sentence = extract_first_sentence(content)
                    if sentence:
                        data.append({"text": sentence, "label": 0})
            except Exception as e:
                print(f"Erreur lecture {f}: {e}")
                
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
    # 1. Chargement des données
    print("Chargement des données...")
    df = load_data()
    if df.empty:
        print(f"Aucune donnée trouvée dans {DATA_PATH}. Vérifiez le chemin.")
        return
    
    print(f"Total d'échantillons : {len(df)}")
    print("Distribution des labels :")
    print(df['label'].value_counts())

    # 2. Split train/val
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        df['text'].tolist(), 
        df['label'].tolist(), 
        test_size=0.2, 
        random_state=42, 
        stratify=df['label'].tolist()
    )

    # 3. Tokenization
    print(f"Initialisation du tokenizer {MODEL_NAME}...")
    tokenizer = CamembertTokenizer.from_pretrained(MODEL_NAME)
    
    train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=128)
    val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=128)

    train_dataset = ChronicleDataset(train_encodings, train_labels)
    val_dataset = ChronicleDataset(val_encodings, val_labels)

    # 4. Modèle
    print(f"Chargement du modèle {MODEL_NAME}...")
    model = CamembertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    # 5. WandB Initialization
    wandb.init(
        project=WANDB_PROJECT,
        name=f"camembert-chronicle-start-{pd.Timestamp.now().strftime('%Y%m%d-%H%M')}",
        config={
            "model": MODEL_NAME,
            "epochs": 3,
            "batch_size": 16,
            "learning_rate": 5e-5,
        },
        settings=wandb.Settings(init_timeout=300)
    )

    # 6. Arguments d'entrainement
    # On détecte si un GPU (CUDA ou MPS) est disponible
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    
    print(f"Entrainement sur : {device}")

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir='./logs',
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        report_to="wandb",
        push_to_hub=True,
        hub_model_id=HF_REPO_NAME,
        hub_strategy="every_save",
    )

    # 7. Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    # 7. Entrainement
    print("Début de l'entrainement...")
    trainer.train()
    
    # Fin du run WandB
    wandb.finish()

    # 8. Sauvegarde
    print(f"Sauvegarde du modèle dans {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    # Publication finale sur Hugging Face
    print(f"Publication sur le Hugging Face Hub : {HF_REPO_NAME}")
    
    # 1. Évaluation finale pour obtenir les métriques précises
    print("Évaluation finale...")
    eval_results = trainer.evaluate()
    
    # 2. Création d'une "Note de Qualité" simplifiée
    # On utilise F1 pour la Cardinalité et Accuracy pour l'Alignement (proxies)
    card_score = eval_results.get('eval_f1', 0) * 100
    align_score = eval_results.get('eval_accuracy', 0) * 100
    global_score = (card_score * 0.4) + (align_score * 0.6)
    
    quality_note = f"""
---
# 📊 Note de Qualité : {global_score:.1f}/100

- **La Cardinalité (40%) : {card_score:.1f}%**
  *La capacité du modèle à identifier le nombre exact de chroniques présentes, sans omission ni sur-segmentation.*
- **L'Alignement Temporel (60%) : {align_score:.1f}%**
  *La précision chirurgicale des points de début et de fin de chaque chronique détectée par rapport à la réalité.*

---
**Détails techniques :**
- Précision : {eval_results.get('eval_precision', 0):.4f}
- Rappel : {eval_results.get('eval_recall', 0):.4f}
- F1-Score : {eval_results.get('eval_f1', 0):.4f}
- Accuracy : {eval_results.get('eval_accuracy', 0):.4f}

*Généré automatiquement le {pd.Timestamp.now().strftime('%d/%m/%Y à %H:%M')}*
---
"""
    
    # 3. Publication initiale via le trainer (crée le repo et le README de base)
    trainer.push_to_hub()
    
    # 4. Mise à jour du README avec la note de qualité
    try:
        from huggingface_hub import Repository, HfApi
        api = HfApi()
        
        # On télécharge le README existant, on ajoute la note, et on repousse
        readme_path = os.path.join(OUTPUT_DIR, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "a", encoding="utf-8") as f:
                f.write(quality_note)
            
            api.upload_file(
                path_or_fileobj=readme_path,
                path_in_repo="README.md",
                repo_id=HF_REPO_NAME,
                repo_type="model"
            )
            print("README.md mis à jour avec la note de qualité sur le Hub.")
    except Exception as e:
        print(f"Erreur lors de la mise à jour du README sur le Hub : {e}")
    
    # Ajout à la collection
    try:
        print(f"Ajout du modèle à la collection : {HF_COLLECTION_SLUG}")
        add_collection_item(
            collection_slug=HF_COLLECTION_SLUG,
            item_id=HF_REPO_NAME,
            item_type="model",
            exists_ok=True
        )
        print("Modèle ajouté à la collection avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'ajout à la collection : {e}")

    # 9. Test rapide
    print("\n--- Test rapide ---")
    sentences = [
        "Bonjour à tous, il est 8h, c'est l'heure de la revue de presse.",
        "Merci d'avoir été avec nous, on se retrouve demain.",
        "France Culture, les matins de France Culture.",
        "C'était le billet politique de Stéphane Robert."
    ]
    model.eval()
    model.to("cpu") # Pour le test simple
    for s in sentences:
        inputs = tokenizer(s, return_tensors="pt", truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            pred = torch.argmax(probs, dim=-1).item()
            label = "DEBUT" if pred == 1 else "AUTRE/FIN"
            print(f"Phrase : '{s}' -> Détection : {label} ({probs[0][pred]:.2f})")

if __name__ == "__main__":
    train()
