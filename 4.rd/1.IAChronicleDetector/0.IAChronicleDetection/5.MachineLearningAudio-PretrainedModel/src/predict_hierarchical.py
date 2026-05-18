import os
import argparse
import json
import torch
import librosa
import numpy as np
from transformers import (
    AutoModelForAudioClassification, 
    AutoFeatureExtractor,
    ASTForAudioClassification,
    ASTFeatureExtractor
)

SAMPLING_RATE = 16000

class HierarchicalDetector:
    def __init__(self, ast_model_path="./model_output_ast", device=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # 1. Level 1: Light model (we use base AST on AudioSet as a robust filter for Speech)
        print("Loading base AST model for Speech/Music filtering...")
        self.filter_extractor = ASTFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")
        self.filter_model = ASTForAudioClassification.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593").to(self.device)
        self.filter_model.eval()
        
        # AudioSet labels for 'Speech' is 0
        self.speech_class_id = 0
        self.music_class_id = 137 # General music class in AudioSet
        
        # 2. Level 2: Specialized model for Chronicles (Fine-tuned AST)
        print(f"Loading specialized chronicle detector from {ast_model_path}...")
        self.ast_extractor = ASTFeatureExtractor.from_pretrained(ast_model_path)
        self.ast_model = ASTForAudioClassification.from_pretrained(ast_model_path).to(self.device)
        self.ast_model.eval()

    def is_speech(self, audio_segment):
        """Returns True if the segment is likely to contain speech."""
        # Simple energy check (Silence detection)
        rms = librosa.feature.rms(y=audio_segment)
        if np.mean(rms) < 0.008: # Slightly higher threshold for silence
            return False, "silence"

        # Level 1: Speech vs Music/Noise Filtering
        inputs = self.filter_extractor(audio_segment, sampling_rate=SAMPLING_RATE, return_tensors="pt",
                                     max_length=int(SAMPLING_RATE * 10.0), padding="max_length", truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            logits = self.filter_model(**inputs).logits
            probs = torch.sigmoid(logits) # AudioSet labels are multi-label
            
        speech_prob = probs[0][self.speech_class_id].item()
        music_prob = probs[0][self.music_class_id].item()
        
        # Logic: If speech is significantly present or more likely than pure music
        if speech_prob > 0.4 and speech_prob > music_prob:
            return True, "speech"
        if music_prob > 0.6:
            return False, "music"
            
        return speech_prob > 0.3, "ambiguous"

    def detect(self, audio_path, window_size=10.0, overlap=5.0, threshold=0.5):
        print(f"Processing audio: {audio_path}")
        audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE)
        duration = len(audio) / SAMPLING_RATE
        step = window_size - overlap
        
        results = []
        
        print("Starting Hierarchical Inference...")
        total_steps = len(np.arange(0, duration - window_size, step))
        count = 0
        for start in np.arange(0, duration - window_size, step):
            count += 1
            if count % 10 == 0:
                print(f"Processed {count}/{total_steps} segments ({(count/total_steps)*100:.1f}%)")
                
            end = start + window_size
            segment = audio[int(start * SAMPLING_RATE):int(end * SAMPLING_RATE)]
            
            # Step 1: Hierarchical Filtering
            likely_speech, reason = self.is_speech(segment)
            
            if not likely_speech:
                # Skip AST classification for non-speech
                continue
                
            # Step 2: Specialized Classification
            inputs = self.ast_extractor(segment, sampling_rate=SAMPLING_RATE, return_tensors="pt", 
                                       max_length=int(SAMPLING_RATE * window_size), padding="max_length", truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                logits = self.ast_model(**inputs).logits
                probs = torch.softmax(logits, dim=-1)
                
            chronique_prob = probs[0][1].item()
            
            if chronique_prob >= threshold:
                results.append({
                    "start": start,
                    "end": end,
                    "confidence": chronique_prob,
                    "type": reason
                })
        
        return self.merge_segments(results)

    def merge_segments(self, segments, gap_filling=2.0, min_duration=10.0):
        if not segments:
            return []
            
        merged = []
        current = segments[0].copy()
        
        for i in range(1, len(segments)):
            next_seg = segments[i]
            if next_seg["start"] <= current["end"] + gap_filling:
                current["end"] = max(current["end"], next_seg["end"])
                current["confidence"] = max(current["confidence"], next_seg["confidence"])
            else:
                merged.append(current)
                current = next_seg.copy()
        merged.append(current)
        
        # Filter by duration
        final = [m for m in merged if (m["end"] - m["start"]) >= min_duration]
        
        # Format timecodes
        for m in final:
            m["start_time"] = self.format_time(m["start"])
            m["end_time"] = self.format_time(m["end"])
            
        return final

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

def main():
    parser = argparse.ArgumentParser(description="Hierarchical Chronicle Detection")
    parser.add_argument("audio", type=str, help="Path to audio file")
    parser.add_argument("--threshold", type=float, default=0.7, help="Confidence threshold for AST")
    parser.add_argument("--output", type=str, default="resultat_hierarchique.json", help="Output JSON file")
    
    args = parser.parse_args()
    
    detector = HierarchicalDetector()
    detections = detector.detect(args.audio, threshold=args.threshold)
    
    print(f"\nDetected {len(detections)} chronicles:")
    for d in detections:
        print(f"  {d['start_time']} - {d['end_time']} (Conf: {d['confidence']:.2f})")
        
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(detections, f, indent=4, ensure_ascii=False)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
