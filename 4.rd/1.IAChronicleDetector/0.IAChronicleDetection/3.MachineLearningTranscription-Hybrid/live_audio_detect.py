import os
import sys
import time
import torch
import json
import numpy as np
from pydub import AudioSegment
from transformers import KyutaiSpeechToTextProcessor, KyutaiSpeechToTextForConditionalGeneration
from typing import List, Dict

# Ajout du dossier courant au path pour les imports locaux
sys.path.append(os.getcwd())
from train import RadioChroniqueClassifier, HybridSequenceClassifier
from utils import extract_features_from_text, format_timecode

class LiveChronicleDetector:
    def __init__(self, base_model_path, hybrid_model_path, stt_model_id="kyutai/stt-1b-en_fr-trfs"):
        self.device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))
        print(f"Initialisation sur {self.device}...")
        
        # 1. Chargement des modèles de détection
        print("Chargement des modèles de détection...")
        self.base_extractor = RadioChroniqueClassifier.load_model(base_model_path)
        self.hybrid_model = HybridSequenceClassifier.load(hybrid_model_path)
        self.hybrid_model.model.to(self.device)
        self.hybrid_model.model.eval()
        
        # 2. Chargement de Kyutai STT
        print(f"Chargement de Kyutai STT ({stt_model_id})...")
        self.stt_processor = KyutaiSpeechToTextProcessor.from_pretrained(stt_model_id)
        self.stt_model = KyutaiSpeechToTextForConditionalGeneration.from_pretrained(
            stt_model_id, 
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        ).to(self.device)
        
        self.seq_len = self.hybrid_model.seq_len
        self.segments_buffer = [] # Liste des segments détectés jusqu'à présent
        self.current_chronicle = None
        self.detected_results = [] # Pour stockage JSON
        self.start_process_time = time.time()
        
    def transcribe_chunk(self, audio_segment):
        # Kyutai attend du 24kHz mono
        audio_segment = audio_segment.set_frame_rate(24000).set_channels(1)
        
        # Convertir pydub AudioSegment en numpy array float32 [-1, 1]
        samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
        # Normalisation selon le format (16-bit int -> float)
        if audio_segment.sample_width == 2:
            samples /= 32768.0
        elif audio_segment.sample_width == 4:
            samples /= 2147483648.0
            
        inputs = self.stt_processor(audio=samples, sampling_rate=24000, return_tensors="pt").to(self.device)
        
        # Gestion du half precision si disponible
        if torch.cuda.is_available() and self.stt_model.dtype == torch.float16:
            inputs = {k: v.to(torch.float16) if v.dtype == torch.float32 else v for k, v in inputs.items()}
            
        with torch.no_grad():
            # Kyutai STT generate attend input_values explicitement ou via **inputs
            generated_ids = self.stt_model.generate(**inputs)
            transcription = self.stt_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
        return transcription.strip()

    def process_audio(self, audio_path, chunk_duration=5.0, output_json="detections.json"):
        print(f"Démarrage de la détection sur {audio_path}")
        self.start_process_time = time.time()
        
        # Chargement avec pydub (supporte m4a via ffmpeg)
        try:
            full_audio = AudioSegment.from_file(audio_path)
        except Exception as e:
            print(f"Erreur lors de l'ouverture du fichier : {e}")
            return

        chunk_ms = int(chunk_duration * 1000)
        current_time_ms = 0
        
        while current_time_ms < len(full_audio):
            start_ms = current_time_ms
            end_ms = min(current_time_ms + chunk_ms, len(full_audio))
            current_time_ms = end_ms
            
            chunk = full_audio[start_ms:end_ms]
            
            start_time_sec = start_ms / 1000.0
            end_time_sec = end_ms / 1000.0
            
            # 1. Transcription
            text = self.transcribe_chunk(chunk)
            if not text:
                continue
            
            print(f"[{format_timecode(start_time_sec)} - {format_timecode(end_time_sec)}] {text}")
            
            # 2. Ajout au buffer
            segment = {
                'start': start_time_sec,
                'end': end_time_sec,
                'text': text
            }
            self.segments_buffer.append(segment)
            
            # 3. Détection
            self.detect_live()
                
        # Finalisation si une chronique est en cours
        if self.current_chronicle:
            self.finalize_chronicle()
            
        # Sauvegarde JSON
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(self.detected_results, f, indent=2, ensure_ascii=False)
        print(f"\n📊 Résultats sauvegardés dans {output_json}")

    def finalize_chronicle(self):
        duration = self.current_chronicle['end'] - self.current_chronicle['start']
        if duration >= 5.0:
            detect_time = time.time() - self.start_process_time
            # Ici on simule le detect_at par rapport au flux audio (current_time_sec)
            # Dans un vrai live, ce serait le temps écoulé depuis le début du script.
            # On va utiliser le temps de fin du segment actuel comme "temps de détection"
            current_audio_time = self.segments_buffer[-1]['end']
            
            result = {
                "label": "Chronique détectée",
                "start": round(self.current_chronicle['start'], 2),
                "end": round(self.current_chronicle['end'], 2),
                "detected_at": round(current_audio_time, 2),
                "confidence": round(self.current_chronicle['conf'], 3)
            }
            self.detected_results.append(result)
            print(f"✅ CHRONIQUE VALIDEE : {format_timecode(result['start'])} -> {format_timecode(result['end'])} (Détectée à {result['detected_at']:.1f}s)")
        else:
            print(f"❌ CHRONIQUE REJETEE (trop courte) : {format_timecode(self.current_chronicle['start'])} -> {format_timecode(self.current_chronicle['end'])}")
        self.current_chronicle = None

    def detect_live(self):
        if len(self.segments_buffer) == 0:
            return
            
        # On prend les derniers seq_len segments
        window = self.segments_buffer[-self.seq_len:]
        
        # Préparation des features
        X_window = self.base_extractor.prepare_features(window, training=False)
        
        # Padding si nécessaire
        if len(X_window) < self.seq_len:
            padding = np.zeros((self.seq_len - len(X_window), X_window.shape[1]))
            X_window = np.vstack([padding, X_window])
            
        X_tensor = torch.FloatTensor(X_window).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            preds = self.hybrid_model.model(X_tensor)[0]
            lstm_out, _ = self.hybrid_model.model.lstm(X_tensor)
            emissions = self.hybrid_model.model.fc(self.hybrid_model.model.dropout(lstm_out))
            probs = torch.softmax(emissions, dim=2)[0, -1, 1].item()
            
        last_pred = preds[-1]
        last_seg = window[-1]
        
        if last_pred > 0: # 1=Start ou 2=Inside
            if self.current_chronicle is None:
                self.current_chronicle = {'start': last_seg['start'], 'end': last_seg['end'], 'conf': probs}
                print(f"🚀 DEBUT CHRONIQUE DETECTE : {format_timecode(last_seg['start'])}")
            else:
                self.current_chronicle['end'] = last_seg['end']
                self.current_chronicle['conf'] = max(self.current_chronicle['conf'], probs)
        else:
            if self.current_chronicle:
                self.finalize_chronicle()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Détection de chroniques en live via Kyutai STT.")
    parser.add_argument("--audio", required=True, help="Chemin vers le fichier audio")
    parser.add_argument("--base", default="models/radio_chronique_hybrid_base.pkl")
    parser.add_argument("--hybrid", default="models/radio_chronique_hybrid_hybrid.pt")
    parser.add_argument("--chunk", type=float, default=5.0, help="Durée des chunks en secondes")
    parser.add_argument("--output", default="detections.json", help="Fichier JSON de sortie")
    
    args = parser.parse_args()
    
    detector = LiveChronicleDetector(args.base, args.hybrid)
    detector.process_audio(args.audio, chunk_duration=args.chunk, output_json=args.output)
