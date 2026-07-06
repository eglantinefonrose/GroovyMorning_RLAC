import argparse
import json
import sys
import os
import requests
import time
import threading
import queue
from pathlib import Path
from faster_whisper import WhisperModel

# Optionnel pour le mode live
try:
    import sounddevice as sd
    import numpy as np
    LIVE_AVAILABLE = True
except ImportError:
    LIVE_AVAILABLE = False

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"

CHRONIQUES = [
    "les 80 secondes", "le grand reportage", "l'édito média", "musicaline",
    "l'édito politique", "l'édito éco", "l'invité de 7h50", 
    "le billet de bertrand chameroy", "le journal de 8h", "geopolitique",
    "l'invité de 8h20", "dans l'oeil de", "un monde nouveau", "le billet de mosimann"
]

def transcribe_audio(audio_path, model_size="base"):
    print(f"Transcription de {audio_path}...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, language="fr")
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]

def analyze_segment_with_llm(phrase, history):
    prompt = f"Voici une nouvelle phrase : \"{phrase}\". Est-ce le début d'une chronique ?"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Tu détectes les débuts de chroniques radio. Réponds en JSON: {\"detecte\": true/false, \"chronique\": \"nom\"}"},
            *history[-10:], # Garder un peu de contexte
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json"
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        return response.json()['message']['content']
    except:
        return "{\"detecte\": false}"

def live_detection(model_size="base"):
    if not LIVE_AVAILABLE:
        print("Erreur: sounddevice et numpy sont requis pour le mode live.", file=sys.stderr)
        return

    print(f"Initialisation Live (Whisper {model_size})...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    audio_queue = queue.Queue()
    history = []

    def audio_callback(indata, frames, time, status):
        audio_queue.put(indata.copy())

    def process_llm(text):
        nonlocal history
        res_raw = analyze_segment_with_llm(text, history)
        try:
            res = json.loads(res_raw)
            if res.get("detecte"):
                print(f"\n🔔 [DÉTECTION] {res.get('chronique')} : \"{text}\"")
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": res_raw})
            if len(history) > 20: history = history[-20:]
        except: pass

    print("🎙️ Écoute activée. Parlez dans le micro...", file=sys.stderr)
    audio_buffer = np.array([], dtype=np.float32)
    sample_rate = 16000

    with sd.InputStream(samplerate=sample_rate, channels=1, callback=audio_callback):
        while True:
            data = audio_queue.get()
            audio_buffer = np.append(audio_buffer, data.flatten())

            if len(audio_buffer) > sample_rate * 2.5: # Analyser par blocs de 2.5s
                segments, _ = model.transcribe(audio_buffer, beam_size=1, language="fr")
                text = " ".join([s.text.strip() for s in segments]).strip()
                if text:
                    print(f"Transcrit: {text}")
                    threading.Thread(target=process_llm, args=(text,), daemon=True).start()
                audio_buffer = np.array([], dtype=np.float32)

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche LLM)")
    parser.add_argument("audio", nargs="?", help="Chemin audio (optionnel si --live)")
    parser.add_argument("--whisper-model", default="base")
    parser.add_argument("--live", action="store_true", help="Mode live (micro)")
    args = parser.parse_args()

    if args.live:
        live_detection(model_size=args.whisper_model)
        return

    if not args.audio or not Path(args.audio).exists():
        parser.print_help()
        sys.exit(1)

    segments = transcribe_audio(args.audio, model_size=args.whisper_model)
    results = []
    history = []
    
    print(f"Analyse LLM avec {MODEL}...", file=sys.stderr)
    for seg in segments:
        res_raw = analyze_segment_with_llm(seg['text'], history)
        try:
            res = json.loads(res_raw)
            if res.get("detecte"):
                results.append({
                    "start": round(seg['start'], 2),
                    "end": round(seg['start'] + 60.0, 2),
                    "label": res.get("chronique", "chronique"),
                    "confidence": 1.0
                })
            history.append({"role": "user", "content": seg['text']})
            history.append({"role": "assistant", "content": res_raw})
        except:
            pass
            
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
