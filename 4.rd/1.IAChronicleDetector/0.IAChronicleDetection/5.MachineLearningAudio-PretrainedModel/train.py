import os
import re
import json
import torch
import librosa
import numpy as np
from datetime import datetime
from pydub import AudioSegment
import evaluate
from datasets import Dataset, Features, Value, Sequence
from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    TrainingArguments,
    Trainer,
    EvalPrediction,
    TrainerCallback
)
from typing import List, Dict

# Configuration
AUDIO_ROOT = "../../../@assets/0.media/audio"
TIMECODE_ROOT = "../../../@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/timecode_chroniques"
MODEL_NAME = "facebook/wav2vec2-large-xlsr-53-french"
OUTPUT_DIR = "./model_output"
SAMPLING_RATE = 16000
MAX_DURATION = 10.0

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

def segment_generator(pairs: List[Dict], label2id: Dict):
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
                    for seg_start in np.arange(start_sec, end_sec - 2.0, 5.0):
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
                for bg_start in np.arange(last_end, start - 10.0, 20.0):
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
    return accuracy_metric.compute(predictions=preds, references=p.label_ids)

class UnfreezeCallback(TrainerCallback):
    def on_epoch_begin(self, args, state, control, **kwargs):
        if state.epoch >= 2:
            model = kwargs.get("model")
            if model:
                print("Unfreezing feature encoder...")
                for param in model.wav2vec2.feature_extractor.parameters():
                    param.requires_grad = True

def train():
    pairs = load_dataset_pairs()
    print(f"Found {len(pairs)} audio/timecode pairs.")
    
    unique_labels = get_unique_labels(pairs)
    label2id = {label: i for i, label in enumerate(unique_labels)}
    id2label = {i: label for i, label in enumerate(unique_labels)}
    
    print(f"Number of unique labels: {len(unique_labels)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "label_mapping.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f)

    features = Features({
        "audio_array": Sequence(Value("float32")),
        "label": Value("int32")
    })

    dataset = Dataset.from_generator(
        segment_generator, 
        gen_kwargs={"pairs": pairs, "label2id": label2id},
        features=features
    )
    
    print(f"Total dataset size: {len(dataset)}")
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
        save_strategy="no",
        learning_rate=5e-5,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        num_train_epochs=10,
        weight_decay=0.01,
        load_best_model_at_end=False,
        metric_for_best_model="accuracy",
        logging_steps=10,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        processing_class=feature_extractor,
        compute_metrics=compute_metrics,
        callbacks=[UnfreezeCallback()]
    )

    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    feature_extractor.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    train()
