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
OUTPUT_DIR = "./model_output_jingle"
SAMPLING_RATE = 16000
JINGLE_DURATION = 1.0  # We assume jingles are in the first second

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

def segment_generator(pairs: List[Dict], label2id: Dict, background_step: float = 30.0, max_samples: int = None):
    """
    Generates samples for Jingle detection.
    - Class 'jingle' (1): First few seconds of each chronicle.
    - Class 'background' (0): Actual background AND middle/end of chronicles.
    """
    count = 0
    for pair in pairs:
        try: 
            audio = AudioSegment.from_file(pair['audio_path'])
        except: 
            continue
            
        chronicle_intervals = []
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                if max_samples and count >= max_samples: return
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    start_sec = parse_timecode(match.group(1))
                    end_sec = parse_timecode(match.group(2))
                    if end_sec <= start_sec: continue
                    chronicle_intervals.append((start_sec, end_sec))
                    
                    # 1. JINGLE: The start of the chronicle
                    jingle_end = min(start_sec + JINGLE_DURATION, end_sec)
                    segment_audio = audio[start_sec*1000:jingle_end*1000]
                    samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                    if segment_audio.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                    samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                    if segment_audio.frame_rate != SAMPLING_RATE:
                        samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                    
                    yield {"audio_array": samples, "label": label2id["jingle"]}
                    count += 1
                    
                    # 2. NON-JINGLE: Sample one segment from the middle of the chronicle as background
                    if end_sec - start_sec > JINGLE_DURATION + 10.0:
                        mid_start = start_sec + JINGLE_DURATION + 5.0
                        mid_end = mid_start + JINGLE_DURATION
                        segment_audio = audio[mid_start*1000:mid_end*1000]
                        samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                        if segment_audio.channels == 2: samples = samples.reshape((-1, 2)).mean(axis=1)
                        samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                        if segment_audio.frame_rate != SAMPLING_RATE:
                            samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                        yield {"audio_array": samples, "label": label2id["background"]}
                        count += 1

        # 3. ACTUAL BACKGROUND: Sample from silence/music between chronicles
        chronicle_intervals.sort()
        last_end = 0
        for start, end in chronicle_intervals:
            if start > last_end + 10.0:
                for bg_start in np.arange(last_end, start - 5.0, background_step):
                    if max_samples and count >= max_samples: return
                    bg_end = bg_start + JINGLE_DURATION
                    if bg_end > start: break
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

def train(epochs=5, cleanup=False, max_samples=4000):
    if cleanup: cleanup_cache()
    
    run_name = f"ast-jingle-detector-{datetime.now().strftime('%d/%m-%H:%M')}"
    pairs = load_dataset_pairs()
    label2id = {"background": 0, "jingle": 1}
    id2label = {0: "background", 1: "jingle"}
    
    print(f"Training Jingle Detector...")
    print(f"Output directory: {OUTPUT_DIR}")

    wandb.init(
        project="RLAC-Jingle", name=run_name, tags=["ast", "jingle"],
        config={
            "model_architecture": "AST", "epochs": epochs,
            "sampling_rate": SAMPLING_RATE, "jingle_duration": JINGLE_DURATION
        }
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f)

    features = Features({"audio_array": Sequence(Value("float32")), "label": Value("int32")})
    dataset = Dataset.from_generator(
        segment_generator, 
        gen_kwargs={"pairs": pairs, "label2id": label2id, "max_samples": max_samples},
        features=features
    ).train_test_split(test_size=0.1)
    
    loader = ModelLoader()
    model, feature_extractor = loader.init_ast(MODEL_NAME, label2id, id2label)

    def preprocess_function(examples):
        return feature_extractor(examples["audio_array"], sampling_rate=SAMPLING_RATE, max_length=int(SAMPLING_RATE * JINGLE_DURATION), truncation=True, padding="max_length")

    dataset = dataset.map(preprocess_function, batched=True, remove_columns=["audio_array"])
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR, eval_strategy="epoch", save_strategy="epoch", learning_rate=5e-5,
        per_device_train_batch_size=2, per_device_eval_batch_size=2,
        gradient_accumulation_steps=8, num_train_epochs=epochs,
        load_best_model_at_end=True, metric_for_best_model="f1", logging_steps=10, report_to="wandb",
        save_total_limit=1, fp16=torch.cuda.is_available()
    )
    
    trainer = Trainer(
        model=model, args=training_args, train_dataset=dataset["train"], eval_dataset=dataset["test"],
        processing_class=feature_extractor, compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )
    
    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    feature_extractor.save_pretrained(OUTPUT_DIR)
    print(f"Jingle model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    train(epochs=args.epochs, cleanup=args.cleanup)
