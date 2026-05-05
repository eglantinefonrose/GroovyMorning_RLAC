import torch
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor
import librosa
import numpy as np

MODEL_DIR = "../model_output"
SAMPLING_RATE = 16000

def test_model(audio_path):
    model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_DIR)
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR)
    model.eval()
    
    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE, duration=60)
    
    for i in range(0, 60, 10):
        segment = audio[i*SAMPLING_RATE : (i+10)*SAMPLING_RATE]
        if len(segment) < SAMPLING_RATE: break
        
        inputs = feature_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt")
        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            
        top_probs, top_ids = torch.topk(probs, 5)
        print(f"\nSegment {i}s - {i+10}s:")
        for p, idx in zip(top_probs[0], top_ids[0]):
            label_id = idx.item()
            label = model.config.id2label.get(label_id, model.config.id2label.get(str(label_id), "Unknown"))
            print(f"  {label}: {p.item():.4f}")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        test_model(sys.argv[1])
    else:
        print("Please provide an audio file path.")
