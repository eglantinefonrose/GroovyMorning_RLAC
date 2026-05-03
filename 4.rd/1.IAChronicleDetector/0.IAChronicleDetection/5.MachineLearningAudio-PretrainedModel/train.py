import os
import re
import json
import torch
import librosa
import numpy as np
import wandb
from datetime import datetime
from pydub import AudioSegment
import evaluate
from datasets import Dataset, Audio
from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    TrainingArguments,
    Trainer,
    EvalPrediction
)
from sklearn.model_selection import train_test_split
from typing import List, Dict

# Configuration
AUDIO_ROOT = "../../../@assets/0.media/audio"
TIMECODE_ROOT = "../../../@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/timecode_chroniques"
MODEL_NAME = "facebook/wav2vec2-large-xlsr-53-french"
OUTPUT_DIR = "./model_output"
SAMPLING_RATE = 16000
MAX_DURATION = 30.0  # seconds (Wav2Vec2 can be memory intensive)

def parse_timecode(tc_str: str) -> float:
    """Converts [HH:MM:SS:mmm] to seconds."""
    parts = tc_str.strip("[] ").split(":")
    if len(parts) == 4:
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000.0
    return 0.0

def load_dataset_pairs():
    data = []
    # Iterate over radios
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
                
                # Find matching audio
                audio_folder = os.path.join(AUDIO_ROOT, radio, date_str)
                if not os.path.exists(audio_folder):
                    continue
                
                audio_files = os.listdir(audio_folder)
                # Rule of priority: _trimmed version
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

def extract_segments(pairs: List[Dict]):
    segments = []
    labels_set = set()
    
    for pair in pairs:
        print(f"Processing {pair['audio_path']}...")
        try:
            audio = AudioSegment.from_file(pair['audio_path'])
        except Exception as e:
            print(f"Error loading {pair['audio_path']}: {e}")
            continue
            
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                # Format: [00:00:00:000] - [00:10:09:800] label.mp3
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    start_str, end_str, label = match.groups()
                    start_sec = parse_timecode(start_str)
                    end_sec = parse_timecode(end_str)
                    label = label.strip().replace(".mp3", "").replace(".m4a", "")
                    
                    if end_sec <= start_sec:
                        continue
                        
                    # Extract segment
                    start_ms = start_sec * 1000
                    end_ms = end_sec * 1000
                    segment_audio = audio[start_ms:end_ms]
                    
                    # Save segment to temp folder or keep in memory? 
                    # Keeping in memory as numpy array for Dataset
                    # Resample to 16kHz
                    samples = np.array(segment_audio.get_array_of_samples()).astype(np.float32)
                    if segment_audio.channels == 2:
                        samples = samples.reshape((-1, 2)).mean(axis=1)
                    
                    # Normalize
                    samples /= np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else 1
                    
                    # Resample if needed
                    if segment_audio.frame_rate != SAMPLING_RATE:
                        samples = librosa.resample(samples, orig_sr=segment_audio.frame_rate, target_sr=SAMPLING_RATE)
                    
                    segments.append({
                        "audio": samples,
                        "label": label
                    })
                    labels_set.add(label)
                    
    return segments, sorted(list(labels_set))

accuracy_metric = evaluate.load("accuracy")

def compute_metrics(p: EvalPrediction):
    preds = np.argmax(p.predictions, axis=1)
    return accuracy_metric.compute(predictions=preds, references=p.label_ids)

def train():
    # Initialize WandB
    wandb.init(project="IAChronicleDetector", name="Wav2Vec2-FineTuning")

    pairs = load_dataset_pairs()
    print(f"Found {len(pairs)} audio/timecode pairs.")
    
    all_segments, unique_labels = extract_segments(pairs)
    print(f"Extracted {len(all_segments)} segments with {len(unique_labels)} unique labels.")
    
    label2id = {label: i for i, label in enumerate(unique_labels)}
    id2label = {i: label for i, label in enumerate(unique_labels)}
    
    # Save mapping
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f)

    # Prepare Dataset
    def gen():
        for seg in all_segments:
            yield {"audio": seg["audio"], "label": label2id[seg["label"]]}

    dataset = Dataset.from_generator(gen)
    dataset = dataset.train_test_split(test_size=0.2)
    
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
    
    def preprocess_function(examples):
        audio_arrays = examples["audio"]
        inputs = feature_extractor(
            audio_arrays, 
            sampling_rate=SAMPLING_RATE, 
            max_length=int(SAMPLING_RATE * MAX_DURATION), 
            truncation=True,
            padding=True
        )
        return inputs

    dataset = dataset.map(preprocess_function, batched=True, remove_columns=["audio"])

    model = Wav2Vec2ForSequenceClassification.from_pretrained(
        MODEL_NAME, 
        num_labels=len(unique_labels),
        label2id=label2id,
        id2label=id2label
    )
    
    # Freeze backbone if needed, but here we fine-tune
    # model.freeze_feature_extractor()

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=3e-5,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        num_train_epochs=5,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_dir="./logs",
        logging_steps=10,
        report_to="wandb",
        push_to_hub=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        tokenizer=feature_extractor,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    
    # Save the final model
    trainer.save_model(OUTPUT_DIR)
    feature_extractor.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    train()
