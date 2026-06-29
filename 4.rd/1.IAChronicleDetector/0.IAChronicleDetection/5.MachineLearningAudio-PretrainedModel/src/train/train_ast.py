import os
import re
import json
import torch
import librosa
import numpy as np
import socket
import argparse
import shutil
import random
import sys
from pathlib import Path
from datetime import datetime

# Add the parent directory (src) to sys.path to allow importing modules from it
sys.path.append(str(Path(__file__).resolve().parent.parent))

from pydub import AudioSegment
import evaluate
from sklearn.metrics import f1_score
import wandb
from datasets import Dataset, Features, Value, Sequence
from transformers import (
    ASTForAudioClassification,
    ASTFeatureExtractor,
    TrainingArguments,
    Trainer,
    EvalPrediction,
    TrainerCallback,
    EarlyStoppingCallback
)
from typing import List, Dict
from models_loader import ModelLoader

# Configuration
AUDIO_ROOT = "../../../@assets/0.media/audio"
TIMECODE_ROOT = "../../../@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/timecode_chroniques"
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
OUTPUT_DIR = "./model_output_ast"
SAMPLING_RATE = 16000
MAX_DURATION = 1.0

def predict_single_file(audio_path, model_type="ast"):
    loader = ModelLoader()
    if model_type == "ast":
        loader.load_ast(OUTPUT_DIR)
    
    model, _ = loader.get_model(model_type)
    if not model:
        print(f"Error: Model {model_type} not found at {OUTPUT_DIR}")
        return

    from predict import predict
    results = predict(audio_path, model_type=model_type, model_dir=OUTPUT_DIR)
    print(f"\nResults for {model_type}:")
    print(json.dumps(results, indent=4, ensure_ascii=False))

def cleanup_cache():
    cache_path = Path.home() / ".cache" / "huggingface" / "datasets" / "generator"
    if cache_path.exists():
        print(f"Cleaning up cache at {cache_path}...")
        try:
            shutil.rmtree(cache_path)
            print("Cache cleaned.")
        except Exception as e:
            print(f"Warning: Could not clean cache: {e}")

def parse_timecode(tc_str: str) -> float:
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
        if not os.path.exists(news_dir): continue
        for tc_file in os.listdir(news_dir):
            if tc_file.endswith("_new_from_audio.txt"):
                date_str = tc_file.replace("_new_from_audio.txt", "")
                audio_folder = os.path.join(AUDIO_ROOT, radio, date_str)
                if not os.path.exists(audio_folder): continue
                audio_files = os.listdir(audio_folder)
                audio_file = None
                trimmed = [f for f in audio_files if "_trimmed" in f and (f.endswith(".mp3") or f.endswith(".m4a"))]
                if trimmed: audio_file = trimmed[0]
                else:
                    others = [f for f in audio_files if (f.endswith(".mp3") or f.endswith(".m4a")) and not f.endswith("_trimmed.mp3") and not f.endswith("_trimmed.m4a")]
                    if others: audio_file = others[0]
                if audio_file:
                    data.append({
                        "radio": radio,
                        "date": date_str,
                        "audio_path": os.path.join(audio_folder, audio_file),
                        "tc_path": os.path.join(news_dir, tc_file)
                    })
    return data

def estimate_counts(pairs, chronicle_step, background_step):
    total_chr = 0
    total_bg = 0
    for pair in pairs:
        chronicle_intervals = []
        try:
            with open(pair['tc_path'], 'r', encoding='utf-8') as f:
                for line in f:
                    match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                    if match:
                        start_sec = parse_timecode(match.group(1))
                        end_sec = parse_timecode(match.group(2))
                        if end_sec > start_sec:
                            chronicle_intervals.append((start_sec, end_sec))
                            total_chr += int(max(0, (end_sec - start_sec - 2.0) // chronicle_step) + 1)
            chronicle_intervals.sort()
            last_end = 0
            for start, end in chronicle_intervals:
                if start > last_end + 5.0:
                    total_bg += int(max(0, (start - 5.0 - last_end) // background_step) + 1)
                last_end = max(last_end, end)
        except: continue
    return total_chr, total_bg

def segment_generator(pairs: List[Dict], label2id: Dict, chronicle_step: float = 10.0, background_step: float = 20.0, 
                      bg_keep_prob: float = 1.0, chr_keep_prob: float = 1.0, max_samples: int = None):
    count = 0
    for pair in pairs:
        try: audio = AudioSegment.from_file(pair['audio_path'])
        except: continue
        chronicle_intervals = []
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                if max_samples and count >= max_samples: return
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    start_str, end_str, label = match.groups()
                    start_sec = parse_timecode(start_str)
                    end_sec = parse_timecode(end_str)
                    if end_sec <= start_sec: continue
                    chronicle_intervals.append((start_sec, end_sec))
                    for seg_start in np.arange(start_sec, end_sec - 2.0, chronicle_step):
                        if max_samples and count >= max_samples: return
                        if random.random() > chr_keep_prob: continue
                        seg_end = min(seg_start + MAX_DURATION, end_sec)
                        if seg_end - seg_start < 2.0: break
                        segment_audio = audio[seg_start*1000:seg_end*1000]
                        samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                        if segment_audio.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                        samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                        if segment_audio.frame_rate != SAMPLING_RATE:
                            samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                        yield {"audio_array": samples, "label": label2id["chronique"]}
                        count += 1
        chronicle_intervals.sort()
        last_end = 0
        for start, end in chronicle_intervals:
            if start > last_end + 5.0:
                for bg_start in np.arange(last_end, start - 5.0, background_step):
                    if max_samples and count >= max_samples: return
                    if random.random() > bg_keep_prob: continue
                    bg_end = min(bg_start + MAX_DURATION, start)
                    if bg_end - bg_start < 2.0: continue
                    segment_audio = audio[bg_start*1000:bg_end*1000]
                    samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                    if segment_audio.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                    samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                    if segment_audio.frame_rate != SAMPLING_RATE:
                        samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                    yield {"audio_array": samples, "label": label2id["background"]}
                    count += 1
            last_end = max(last_end, end)

accuracy_metric = evaluate.load("accuracy")
def compute_metrics(p: EvalPrediction):
    preds = np.argmax(p.predictions, axis=1)
    acc = accuracy_metric.compute(predictions=preds, references=p.label_ids)
    f1 = f1_score(p.label_ids, preds, average='binary') 
    return {"accuracy": acc["accuracy"], "f1": f1}

class UnfreezeCallback(TrainerCallback):
    def on_epoch_begin(self, args, state, control, **kwargs):
        if state.epoch >= 2:
            model = kwargs.get("model")
            if model and hasattr(model, "audio_spectrogram_transformer"):
                print("Unfreezing AST encoder...")
                for param in model.audio_spectrogram_transformer.parameters():
                    param.requires_grad = True

def train(epochs=10, tags=None, chronicle_step=1.0, background_step=20.0, background_percent=None, cleanup=False, model_path=None, max_samples=8000):
    if cleanup: cleanup_cache()
    # hardware info
    hardware_info = "CPU"
    if torch.cuda.is_available(): hardware_info = torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available(): hardware_info = "Mac Apple Silicon (MPS)"
    
    run_name = f"ast-chronicle-detector-{datetime.now().strftime('%d/%m-%H:%M')}"
    pairs = load_dataset_pairs()
    label2id = {"background": 0, "chronique": 1}
    id2label = {0: "background", 1: "chronique"}
    
    bg_keep_prob, chr_keep_prob = 1.0, 1.0
    if background_percent is not None:
        n_chr_est, n_bg_est = estimate_counts(pairs, chronicle_step, background_step)
        target_bg_ratio = background_percent / 100.0
        if n_bg_est > 0 and n_chr_est > 0:
            current_bg_ratio = n_bg_est / (n_bg_est + n_chr_est)
            if current_bg_ratio < target_bg_ratio:
                chr_keep_prob = (n_bg_est * (1 - target_bg_ratio) / target_bg_ratio) / n_chr_est
            else:
                bg_keep_prob = (n_chr_est * target_bg_ratio / (1 - target_bg_ratio)) / n_bg_est

    wandb.init(
        project="RLAC-Audio", name=run_name, tags=["ast"] + (tags if tags else []),
        config={
            "model_architecture": "AST", "model_variant": model_path or MODEL_NAME, "epochs": epochs,
            "per_device_train_batch_size": 1, "gradient_accumulation_steps": 16, "learning_rate": 5e-5,
            "hardware": hardware_info, "sampling_rate": SAMPLING_RATE, "max_duration": MAX_DURATION
        }
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f)

    features = Features({"audio_array": Sequence(Value("float32")), "label": Value("int32")})
    dataset = Dataset.from_generator(
        segment_generator, 
        gen_kwargs={"pairs": pairs, "label2id": label2id, "chronicle_step": chronicle_step, "background_step": background_step, "bg_keep_prob": bg_keep_prob, "chr_keep_prob": chr_keep_prob, "max_samples": max_samples},
        features=features
    ).train_test_split(test_size=0.1)
    
    loader = ModelLoader()
    model, feature_extractor = loader.init_ast(model_path or MODEL_NAME, label2id, id2label)

    def preprocess_function(examples):
        return feature_extractor(examples["audio_array"], sampling_rate=SAMPLING_RATE, max_length=int(SAMPLING_RATE * MAX_DURATION), truncation=True, padding="max_length")

    dataset = dataset.map(preprocess_function, batched=True, remove_columns=["audio_array"])
    
    # Freeze the base model
    for param in model.audio_spectrogram_transformer.parameters():
        param.requires_grad = False

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR, eval_strategy="epoch", save_strategy="epoch", learning_rate=5e-5,
        per_device_train_batch_size=1, 
        per_device_eval_batch_size=1,        # Réduit pour éviter OOM sur Mac
        gradient_accumulation_steps=16, num_train_epochs=epochs,
        load_best_model_at_end=True, metric_for_best_model="f1", logging_steps=10, report_to="wandb",
        save_total_limit=1, fp16=torch.cuda.is_available(),
        dataloader_pin_memory=False, 
        eval_accumulation_steps=1            # Déplace immédiatement les prédictions sur CPU
    )
    trainer = Trainer(
        model=model, args=training_args, train_dataset=dataset["train"], eval_dataset=dataset["test"],
        processing_class=feature_extractor, compute_metrics=compute_metrics,
        callbacks=[UnfreezeCallback(), EarlyStoppingCallback(early_stopping_patience=3)]
    )
    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    feature_extractor.save_pretrained(OUTPUT_DIR)

    # Cleanup checkpoints
    for path in Path(OUTPUT_DIR).glob("checkpoint-*"):
        if path.is_dir():
            shutil.rmtree(path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--background_percent", type=float, default=None)
    parser.add_argument("--predict", type=str, help="Path to audio file for prediction")
    parser.add_argument("--model_path", type=str, help="Path to base model for fine-tuning")
    args = parser.parse_args()
    
    if args.predict:
        predict_single_file(args.predict)
    else:
        train(epochs=args.epochs, background_percent=args.background_percent, model_path=args.model_path)
