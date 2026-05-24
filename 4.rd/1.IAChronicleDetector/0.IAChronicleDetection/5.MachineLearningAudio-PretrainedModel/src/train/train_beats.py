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
    AutoModelForAudioClassification,
    AutoFeatureExtractor,
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
MODEL_NAME = "microsoft/beats-base"
OUTPUT_DIR = "./model_output_beats"
SAMPLING_RATE = 16000
MAX_DURATION = 10.0

def predict_single_file(audio_path, model_type="beats"):
    loader = ModelLoader()
    if model_type == "beats":
        loader.load_beats(OUTPUT_DIR)
    
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
        shutil.rmtree(cache_path, ignore_errors=True)

def parse_timecode(tc_str: str) -> float:
    parts = tc_str.strip("[] ").split(":")
    if len(parts) == 4:
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000.0
    return 0.0

def load_dataset_pairs():
    data = []
    if not os.path.exists(TIMECODE_ROOT): return []
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
                audio_file = next((f for f in audio_files if "_trimmed" in f and (f.endswith(".mp3") or f.endswith(".m4a"))), None)
                if not audio_file:
                    audio_file = next((f for f in audio_files if (f.endswith(".mp3") or f.endswith(".m4a")) and not "_trimmed" in f), None)
                if audio_file:
                    data.append({"audio_path": os.path.join(audio_folder, audio_file), "tc_path": os.path.join(news_dir, tc_file)})
    return data

def estimate_counts(pairs, chronicle_step, background_step):
    total_chr, total_bg = 0, 0
    for pair in pairs:
        intervals = []
        try:
            with open(pair['tc_path'], 'r', encoding='utf-8') as f:
                for line in f:
                    m = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]", line)
                    if m:
                        s, e = parse_timecode(m.group(1)), parse_timecode(m.group(2))
                        if e > s:
                            intervals.append((s, e))
                            total_chr += int(max(0, (e - s - 2.0) // chronicle_step) + 1)
            intervals.sort()
            last = 0
            for s, e in intervals:
                if s > last + 5.0: total_bg += int(max(0, (s - 5.0 - last) // background_step) + 1)
                last = max(last, e)
        except: continue
    return total_chr, total_bg

def segment_generator(pairs, label2id, chronicle_step=10.0, background_step=20.0, bg_keep_prob=1.0, chr_keep_prob=1.0, max_samples=None):
    count = 0
    for pair in pairs:
        try: audio = AudioSegment.from_file(pair['audio_path'])
        except: continue
        intervals = []
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                if max_samples and count >= max_samples: return
                m = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]", line)
                if m:
                    s, e = parse_timecode(m.group(1)), parse_timecode(m.group(2))
                    if e <= s: continue
                    intervals.append((s, e))
                    for seg_s in np.arange(s, e - 2.0, chronicle_step):
                        if max_samples and count >= max_samples: return
                        if random.random() > chr_keep_prob: continue
                        seg_e = min(seg_s + MAX_DURATION, e)
                        seg = audio[seg_s*1000:seg_e*1000]
                        samples = np.array(seg.get_array_of_samples()).astype(np.float32)
                        if seg.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                        samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                        if seg.frame_rate != SAMPLING_RATE: samples = librosa.resample(samples, orig_sr=seg.frame_rate, target_sr=SAMPLING_RATE)
                        yield {"audio_array": samples, "label": label2id["chronique"]}
                        count += 1
        intervals.sort()
        last = 0
        for s, e in intervals:
            if s > last + 5.0:
                for bg_s in np.arange(last, s - 5.0, background_step):
                    if max_samples and count >= max_samples: return
                    if random.random() > bg_keep_prob: continue
                    bg_e = min(bg_s + MAX_DURATION, s)
                    seg = audio[bg_s*1000:bg_e*1000]
                    samples = np.array(seg.get_array_of_samples()).astype(np.float32)
                    if seg.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                    samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                    if seg.frame_rate != SAMPLING_RATE: samples = librosa.resample(samples, orig_sr=seg.frame_rate, target_sr=SAMPLING_RATE)
                    yield {"audio_array": samples, "label": label2id["background"]}
                    count += 1
            last = max(last, e)

def compute_metrics(p):
    preds = np.argmax(p.predictions, axis=1)
    f1 = f1_score(p.label_ids, preds, average='binary') 
    return {"accuracy": (preds == p.label_ids).astype(float).mean(), "f1": f1}

class UnfreezeCallback(TrainerCallback):
    def on_epoch_begin(self, args, state, control, **kwargs):
        if state.epoch >= 2:
            model = kwargs.get("model")
            if model:
                print("Unfreezing BEATs encoder...")
                # Generic unfreeze for AutoModel base
                for name, param in model.named_parameters():
                    if "classifier" not in name: param.requires_grad = True

def train(epochs=10, background_percent=None, model_path=None, max_samples=8000, chronicle_step=10.0, background_step=20.0):
    cleanup_cache()
    run_name = f"beats-chronicle-detector-{datetime.now().strftime('%d/%m-%H:%M')}"
    pairs = load_dataset_pairs()
    label2id, id2label = {"background": 0, "chronique": 1}, {0: "background", 1: "chronique"}
    bg_prob, chr_prob = 1.0, 1.0
    if background_percent is not None:
        n_c, n_b = estimate_counts(pairs, chronicle_step, background_step)
        target = background_percent / 100.0
        if n_b > 0 and n_c > 0:
            if n_b/(n_b+n_c) < target: chr_prob = (n_b*(1-target)/target)/n_c
            else: bg_prob = (n_c*target/(1-target))/n_b

    wandb.init(project="RLAC-Audio", name=run_name, tags=["beats"], config={"model": model_path or MODEL_NAME, "epochs": epochs})
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f: json.dump({"label2id": label2id, "id2label": id2label}, f)

    features = Features({"audio_array": Sequence(Value("float32")), "label": Value("int32")})
    ds = Dataset.from_generator(segment_generator, gen_kwargs={"pairs": pairs, "label2id": label2id, "bg_keep_prob": bg_prob, "chr_keep_prob": chr_prob, "max_samples": max_samples, "chronicle_step": chronicle_step, "background_step": background_step}, features=features).train_test_split(test_size=0.1)
    
    loader = ModelLoader()
    model, extractor = loader.init_beats(model_path or MODEL_NAME, label2id, id2label)

    def preprocess(ex): return extractor(ex["audio_array"], sampling_rate=SAMPLING_RATE, max_length=int(SAMPLING_RATE*MAX_DURATION), truncation=True, padding="max_length")
    ds = ds.map(preprocess, batched=True, remove_columns=["audio_array"])
    
    # Freeze base
    for name, param in model.named_parameters():
        if "classifier" not in name: param.requires_grad = False

    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=5e-5,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,        # Réduit pour éviter OOM sur Mac
        gradient_accumulation_steps=16,
        num_train_epochs=epochs,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        report_to="wandb",
        save_total_limit=1,
        fp16=torch.cuda.is_available(),
        dataloader_pin_memory=False,
        eval_accumulation_steps=1            # Déplace immédiatement les prédictions sur CPU
    )
    trainer = Trainer(model=model, args=args, train_dataset=ds["train"], eval_dataset=ds["test"], compute_metrics=compute_metrics, callbacks=[UnfreezeCallback(), EarlyStoppingCallback(early_stopping_patience=3)])
    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    extractor.save_pretrained(OUTPUT_DIR)

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
