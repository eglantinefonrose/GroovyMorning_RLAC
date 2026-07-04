import argparse
import json
import sys
import os
import requests
import time
from pathlib import Path
from faster_whisper import WhisperModel

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

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche LLM Simulation)")
    parser.add_argument("audio", help="Chemin audio")
    parser.add_argument("--whisper-model", default="base")
    args = parser.parse_args()

    if not Path(args.audio).exists():
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
