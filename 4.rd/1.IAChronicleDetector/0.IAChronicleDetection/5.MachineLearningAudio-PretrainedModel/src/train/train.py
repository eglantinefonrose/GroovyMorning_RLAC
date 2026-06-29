import os
import re
import json
import torch
import librosa
import numpy as np
import socket
import argparse
import shutil
from pathlib import Path
from datetime import datetime
from pydub import AudioSegment
import evaluate
from sklearn.metrics import f1_score, classification_report
import wandb
from datasets import Dataset, Features, Value, Sequence
from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    TrainingArguments,
    Trainer,
    EvalPrediction,
    TrainerCallback,
    EarlyStoppingCallback
)
from typing import List, Dict

# Configuration
AUDIO_ROOT = "../../../@assets/0.media/audio"
TIMECODE_ROOT = "../../../@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/timecode_chroniques"
MODEL_NAME = "facebook/wav2vec2-large-xlsr-53-french"
OUTPUT_DIR = "../model_output"
SAMPLING_RATE = 16000
MAX_DURATION = 10.0

def cleanup_cache():
    """Cleans up the Hugging Face generator cache to free disk space."""
    cache_path = Path.home() / ".cache" / "huggingface" / "datasets" / "generator"
    if cache_path.exists():
        print(f"Cleaning up cache at {cache_path}...")
        try:
            shutil.rmtree(cache_path)
            print("Cache cleaned.")
        except Exception as e:
            print(f"Warning: Could not clean cache: {e}")

def parse_timecode(tc_str: str) -> float:
    """Converts [HH:MM:SS:mmm] to seconds."""
    parts = tc_str.strip("[] ").split(":")
    if len(parts) == 4:
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000.0
    return 0.0

def load_dataset_pairs():
    data = []
    if not os.path.exists(TIMECODE_ROOT):
        print(f"Error: {TIMECODE_ROOT} not found.")
        return []

    radios = [d for d in os.listdir(TIMECODE_ROOT) if os.path.isdir(os.path.join(TIMECODE_ROOT, d))]
    
    for radio in radios:
        news_dir = os.path.join(TIMECODE_ROOT, radio, "news")
        if not os.path.exists(news_dir):
            continue
            
        for tc_file in os.listdir(news_dir):
            if tc_file.endswith("_new_from_audio.txt"):
                date_str = tc_file.replace("_new_from_audio.txt", "")
                audio_folder = os.path.join(AUDIO_ROOT, radio, date_str)
                if not os.path.exists(audio_folder):
                    continue
                
                audio_files = os.listdir(audio_folder)
                audio_file = None
                trimmed = [f for f in audio_files if "_trimmed" in f and (f.endswith(".mp3") or f.endswith(".m4a"))]
                if trimmed:
                    audio_file = trimmed[0]
                else:
                    others = [f for f in audio_files if (f.endswith(".mp3") or f.endswith(".m4a")) and not f.endswith("_trimmed.mp3") and not f.endswith("_trimmed.m4a")]
                    if others:
                        audio_file = others[0]
                
                if audio_file:
                    data.append({
                        "radio": radio,
                        "date": date_str,
                        "audio_path": os.path.join(audio_folder, audio_file),
                        "tc_path": os.path.join(news_dir, tc_file)
                    })
    return data

def clean_label(label: str) -> str:
    label = label.strip().replace(".mp3", "").replace(".m4a", "")
    # Consolidation rules
    if re.search(r"journal.*7\s*h", label, re.I): return "journal-7h"
    if re.search(r"journal.*8\s*h", label, re.I): return "journal-8h"
    if re.search(r"journal.*9\s*h", label, re.I): return "journal-9h"
    if "laurent" in label.lower() and "gerra" in label.lower(): return "laurent-gerra"
    if "edito" in label.lower() and "etienne" in label.lower(): return "edito-etienne-gernelle"
    if "vrai" in label.lower() and "faux" in label.lower(): return "le-vrai-du-faux"
    if "angle" in label.lower() and "eco" in label.lower(): return "l-angle-eco"
    if "pepite" in label.lower(): return "la-pepite"
    if "ca-va-mieux" in label.lower() or "ca-va-beaucoup-mieux" in label.lower(): return "ca-va-mieux"
    if "oeil" in label.lower() and "philippe" in label.lower(): return "oeil-philippe"
    if "rtl-evenement" in label.lower() or "rtl_evenement" in label.lower(): return "rtl-evenement"
    
    return label.replace("_", "-")

def get_unique_labels(pairs: List[Dict]):
    labels_set = {"background"}
    for pair in pairs:
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    _, _, label = match.groups()
                    labels_set.add(clean_label(label))
    return sorted(list(labels_set))

def segment_generator(pairs: List[Dict], label2id: Dict, chronicle_step: float = 5.0, background_step: float = 20.0):
    for pair in pairs:
        print(f"\n--- Analysing pair ---")
        print(f"Audio: {pair['audio_path']}")
        print(f"Timecodes: {pair['tc_path']}")
        print(f"----------------------")
        try:
            audio = AudioSegment.from_file(pair['audio_path'])
        except Exception as e:
            print(f"Error loading {pair['audio_path']}: {e}")
            continue
            
        chronicle_intervals = []
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    start_str, end_str, label = match.groups()
                    start_sec = parse_timecode(start_str)
                    end_sec = parse_timecode(end_str)
                    label_name = clean_label(label)
                    
                    if end_sec <= start_sec:
                        continue
                    
                    chronicle_intervals.append((start_sec, end_sec))
                    
                    # Sample multiple segments from the chronicle
                    for seg_start in np.arange(start_sec, end_sec - 2.0, chronicle_step):
                        seg_end = min(seg_start + MAX_DURATION, end_sec)
                        if seg_end - seg_start < 2.0: break
                        
                        start_ms = seg_start * 1000
                        end_ms = seg_end * 1000
                        segment_audio = audio[start_ms:end_ms]
                        
                        samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                        if segment_audio.channels == 2:
                            samples = samples.reshape((-1, 2)).mean(axis=1)
                        samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                        
                        if segment_audio.frame_rate != SAMPLING_RATE:
                            samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                        
                        yield {
                            "audio_array": samples.tolist(),
                            "label": label2id.get(label_name, label2id["background"])
                        }

        # Add background segments
        chronicle_intervals.sort()
        last_end = 0
        for start, end in chronicle_intervals:
            if start > last_end + 10.0:
                for bg_start in np.arange(last_end, start - 10.0, background_step):
                    bg_end = bg_start + MAX_DURATION
                    start_ms = bg_start * 1000
                    end_ms = bg_end * 1000
                    segment_audio = audio[start_ms:end_ms]
                    samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                    if segment_audio.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                    samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                    if segment_audio.frame_rate != SAMPLING_RATE:
                        samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                    yield {
                        "audio_array": samples.tolist(),
                        "label": label2id["background"]
                    }
            last_end = max(last_end, end)

accuracy_metric = evaluate.load("accuracy")

def compute_metrics(p: EvalPrediction):
    preds = np.argmax(p.predictions, axis=1)
    labels = p.label_ids
    
    acc = accuracy_metric.compute(predictions=preds, references=labels)
    f1 = f1_score(labels, preds, average='weighted')
    
    return {
        "accuracy": acc["accuracy"],
        "f1": f1
    }

class UnfreezeCallback(TrainerCallback):
    def on_epoch_begin(self, args, state, control, **kwargs):
        if state.epoch >= 2:
            model = kwargs.get("model")
            if model:
                print("Unfreezing feature encoder...")
                for param in model.wav2vec2.feature_extractor.parameters():
                    param.requires_grad = True

def train(epochs=10, tags=None, chronicle_step=5.0, background_step=20.0, background_percent=None, cleanup=False):
    if cleanup:
        cleanup_cache()
        
    # Détection automatique du matériel
    hardware_info = "CPU"
    if torch.cuda.is_available():
        hardware_info = torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available():
        hardware_info = "Mac Apple Silicon (MPS)"

    # Nom du run explicite
    short_model_name = MODEL_NAME.split('/')[-1]
    run_name = f"{short_model_name}-audio-{datetime.now().strftime('%d/%m-%H:%M')}"

    pairs = load_dataset_pairs()
    print(f"Found {len(pairs)} audio/timecode pairs.")
    
    unique_labels = get_unique_labels(pairs)
    label2id = {label: i for i, label in enumerate(unique_labels)}
    id2label = {i: label for i, label in enumerate(unique_labels)}
    
    print(f"Number of unique labels: {len(unique_labels)}")

    # Initialisation de WandB
    wandb.init(
        project="RLAC-Audio",
        name=run_name,
        tags=tags if tags else [],
        config={
            "model_architecture": "Wav2Vec2",
            "model_variant": MODEL_NAME,
            "epochs": epochs,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 16,
            "learning_rate": 5e-5,
            "dataset_size": len(pairs),
            "machine": socket.gethostname(),
            "hardware": hardware_info,
            "sampling_rate": SAMPLING_RATE,
            "max_duration": MAX_DURATION,
            "chronicle_step": chronicle_step,
            "background_step": background_step,
            "background_percent": background_percent
        }
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f)

    features = Features({
        "audio_array": Sequence(Value("float32")),
        "label": Value("int32")
    })

    dataset = Dataset.from_generator(
        segment_generator, 
        gen_kwargs={"pairs": pairs, "label2id": label2id, "chronicle_step": chronicle_step, "background_step": background_step},
        features=features
    )
    
    print(f"Initial dataset size: {len(dataset)}")

    if background_percent is not None:
        print(f"Balancing dataset to {background_percent}% background...")
        bg_label = label2id["background"]
        labels = np.array(dataset["label"])
        bg_indices = np.where(labels == bg_label)[0]
        chr_indices = np.where(labels != bg_label)[0]
        
        n_bg = len(bg_indices)
        n_chr = len(chr_indices)
        print(f"Counts before balancing - Background: {n_bg}, Chroniques (all types): {n_chr}")
        
        target_bg_ratio = background_percent / 100.0
        
        if n_bg > 0 and n_chr > 0:
            current_bg_ratio = n_bg / (n_bg + n_chr)
            if current_bg_ratio < target_bg_ratio:
                # Too many chronicles, downsample them
                n_chr_target = int(n_bg * (1 - target_bg_ratio) / target_bg_ratio)
                if n_chr_target < n_chr:
                    print(f"Downsampling chronicles to {n_chr_target}")
                    sampled_chr_indices = np.random.choice(chr_indices, n_chr_target, replace=False)
                    indices = np.concatenate([bg_indices, sampled_chr_indices])
                    dataset = dataset.select(indices)
            else:
                # Too many background, downsample them
                n_bg_target = int(n_chr * target_bg_ratio / (1 - target_bg_ratio))
                if n_bg_target < n_bg:
                    print(f"Downsampling background to {n_bg_target}")
                    sampled_bg_indices = np.random.choice(bg_indices, n_bg_target, replace=False)
                    indices = np.concatenate([sampled_bg_indices, chr_indices])
                    dataset = dataset.select(indices)
        
        print(f"Dataset size after balancing: {len(dataset)}")

    dataset = dataset.train_test_split(test_size=0.1)
    
    try:
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME, local_files_only=True)
    except Exception:
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
    
    def preprocess_function(examples):
        inputs = feature_extractor(
            examples["audio_array"], 
            sampling_rate=SAMPLING_RATE, 
            max_length=int(SAMPLING_RATE * MAX_DURATION), 
            truncation=True,
            padding=True
        )
        return inputs

    dataset = dataset.map(preprocess_function, batched=True, remove_columns=["audio_array"])

    try:
        model = Wav2Vec2ForSequenceClassification.from_pretrained(
            MODEL_NAME, 
            num_labels=len(unique_labels),
            label2id=label2id,
            id2label=id2label,
            local_files_only=True
        )
    except Exception:
        model = Wav2Vec2ForSequenceClassification.from_pretrained(
            MODEL_NAME, 
            num_labels=len(unique_labels),
            label2id=label2id,
            id2label=id2label
        )

    model.freeze_feature_encoder()

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        num_train_epochs=epochs,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=10,
        report_to="wandb",
        run_name=run_name,
        save_total_limit=2,
        dataloader_pin_memory=False,
        eval_accumulation_steps=50
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        processing_class=feature_extractor,
        compute_metrics=compute_metrics,
        callbacks=[UnfreezeCallback(), EarlyStoppingCallback(early_stopping_patience=3)]
    )

    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    feature_extractor.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entraînement du détecteur audio de chroniques (Wav2Vec2)")
    parser.add_argument("--epochs", type=int, default=10, help="Nombre d'époques")
    parser.add_argument("--tags", type=str, default="", help="Tags séparés par des virgules pour WandB")
    parser.add_argument("--chronicle_step", type=float, default=5.0, help="Pas d'échantillonnage pour les chroniques (en s)")
    parser.add_argument("--background_step", type=float, default=20.0, help="Pas d'échantillonnage pour le background (en s)")
    parser.add_argument("--background_percent", type=float, default=None, help="Pourcentage de background dans le dataset final")
    parser.add_argument("--cleanup_cache", action="store_true", help="Vider le cache Hugging Face avant de commencer")
    
    args = parser.parse_args()
    
    # Transformation de la string des tags en liste
    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    
    train(
        epochs=args.epochs, 
        tags=tags_list, 
        chronicle_step=args.chronicle_step, 
        background_step=args.background_step,
        background_percent=args.background_percent,
        cleanup=args.cleanup_cache
    )
