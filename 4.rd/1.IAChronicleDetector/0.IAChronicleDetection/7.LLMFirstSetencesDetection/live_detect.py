import sounddevice as sd
import numpy as np
import json
import requests
import threading
import queue
import time
import sys
from faster_whisper import WhisperModel

# Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"
WHISPER_MODEL_SIZE = "base"
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000
SILENCE_THRESHOLD = 0.01
OUTPUT_FILE = "detections_live.json"

# File d'attente pour l'audio capturé
audio_queue = queue.Queue()

# Historique et résultats
history = []
all_detections = []
session_start_time = None
total_samples_processed = 0

def save_detections():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_detections, f, ensure_ascii=False, indent=2)

def analyze_segment_with_llm(phrase, segment_start_offset):
    global history, all_detections
    prompt = f"Voici une nouvelle phrase : \"{phrase}\". Est-ce le début d'une chronique ?"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Tu détectes les débuts de chroniques radio. Réponds UNIQUEMENT en JSON: {\"detecte\": true/false, \"chronique\": \"nom\"}"},
            *history[-6:],
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json"
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=5)
        res_raw = response.json()['message']['content']
        res = json.loads(res_raw)
        
        detected_at = time.time() - session_start_time
        
        if res.get("detecte"):
            label = res.get("chronique", "chronique")
            print(f"\n[!!!] CHRONIQUE DÉTECTÉE : {label} [!!!]")
            print(f"Phrase : {phrase}\n")
            
            detection = {
                "label": label,
                "start": round(segment_start_offset, 2),
                "end": round(segment_start_offset + 60.0, 2), # Estimation par défaut
                "detected_at": round(detected_at, 2),
                "confidence": 1.0
            }
            all_detections.append(detection)
            save_detections()
            
        history.append({"role": "user", "content": phrase})
        history.append({"role": "assistant", "content": res_raw})
        if len(history) > 20: history = history[-20:]
    except Exception as e:
        pass

def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def process_audio(file_path=None):
    global total_samples_processed, session_start_time
    print(f"Chargement de Whisper ({WHISPER_MODEL_SIZE})...")
    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    
    session_start_time = time.time()
    
    if file_path:
        print(f"Analyse du fichier (mode simulé) : {file_path}")
        import librosa
        # Charger l'audio et le mettre dans la file par blocs
        audio, _ = librosa.load(file_path, sr=SAMPLE_RATE)
        # On simule le débit temps réel ou on va le plus vite possible ?
        # Ici on va le plus vite possible pour remplir la file
        for i in range(0, len(audio), BLOCK_SIZE):
            block = audio[i:i+BLOCK_SIZE].reshape(-1, 1)
            audio_queue.put(block)
    else:
        print("Ecoute en cours... (Ctrl+C pour arrêter)")
    
    audio_buffer = np.array([], dtype=np.float32)
    
    while True:
        try:
            # Si on est en mode fichier et que la file est vide
            if file_path and audio_queue.empty():
                # On traite ce qui reste dans le buffer avant de quitter
                if len(audio_buffer) > 0:
                    segments, _ = model.transcribe(audio_buffer, beam_size=1, language="fr")
                    text = "".join([s.text for s in segments]).strip()
                    if text:
                        print(f"[{round(total_samples_processed/SAMPLE_RATE, 1)}s] Final: {text}")
                        analyze_segment_with_llm(text, total_samples_processed/SAMPLE_RATE)
                
                print("\nFin du traitement du fichier.")
                break

            data = audio_queue.get()
            audio_buffer = np.append(audio_buffer, data.flatten())
            
            # Temps écoulé au début de ce buffer
            current_offset = total_samples_processed / SAMPLE_RATE
            
            if len(audio_buffer) > SAMPLE_RATE * 3: # Un peu plus long pour éviter les micro-coupes
                last_samples = audio_buffer[-int(SAMPLE_RATE * 0.5):]
                if np.max(np.abs(last_samples)) < SILENCE_THRESHOLD or len(audio_buffer) > SAMPLE_RATE * 12:
                    
                    segments, _ = model.transcribe(audio_buffer, beam_size=1, language="fr")
                    text = "".join([s.text for s in segments]).strip()
                    
                    if text:
                        print(f"[{round(current_offset, 1)}s] Transcrit: {text}")
                        # En mode fichier, on peut appeler en synchrone ou limiter les threads
                        # Pour éviter de bloquer la console, on garde un thread
                        threading.Thread(target=analyze_segment_with_llm, args=(text, current_offset), daemon=True).start()
                        
                    total_samples_processed += len(audio_buffer)
                    audio_buffer = np.array([], dtype=np.float32)
                    
        except Exception as e:
            print(f"Erreur process: {e}")
            if file_path: break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Chemin vers un fichier audio à analyser à la place du micro")
    args = parser.parse_args()

    try:
        # Démarrer le thread de traitement
        threading.Thread(target=process_audio, args=(args.file,), daemon=True).start()
        
        if not args.file:
            # Démarrer la capture audio (uniquement si pas de fichier)
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback, blocksize=BLOCK_SIZE):
                while True:
                    time.sleep(0.1)
        else:
            # En mode fichier, on attend juste que le thread de traitement finisse
            while threading.active_count() > 1:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nArrêt.")
