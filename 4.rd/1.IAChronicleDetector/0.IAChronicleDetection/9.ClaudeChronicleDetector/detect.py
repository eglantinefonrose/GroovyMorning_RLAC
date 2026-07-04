import argparse
import json
import sys
import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-3-opus-20240229"

def transcribe_audio(audio_path, model_size="base"):
    print(f"Transcription de {audio_path}...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, language="fr")
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]

def analyze_with_claude(phrase, history):
    if not ANTHROPIC_API_KEY:
        return "{\"detecte\": false}"
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    system_prompt = "Tu es un expert radio. Détecte si la phrase suivante est le début d'une chronique. Réponds UNIQUEMENT en JSON: {\"detecte\": true/false, \"chronique\": \"nom\"}"
    
    messages = []
    for h in history[-5:]:
        messages.append(h)
    messages.append({"role": "user", "content": f"Phrase: \"{phrase}\""})
    
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": messages,
        "system": system_prompt
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()['content'][0]['text']
    except:
        return "{\"detecte\": false}"

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche Claude)")
    parser.add_argument("audio", help="Chemin audio")
    parser.add_argument("--whisper-model", default="base")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("Erreur: ANTHROPIC_API_KEY non trouvée", file=sys.stderr)
        sys.exit(1)

    segments = transcribe_audio(args.audio, model_size=args.whisper_model)
    results = []
    history = []
    
    print(f"Analyse avec Claude {MODEL}...", file=sys.stderr)
    for seg in segments:
        res_raw = analyze_with_claude(seg['text'], history)
        try:
            res = json.loads(res_raw)
            if res.get("detecte"):
                results.append({
                    "start": round(seg['start'], 2),
                    "end": round(seg['start'] + 60.0, 2),
                    "label": res.get("chronique", "chronique"),
                    "confidence": 1.0
                })
            history.append({"role": "user", "content": f"Phrase: \"{seg['text']}\""})
            history.append({"role": "assistant", "content": res_raw})
        except:
            pass
        time.sleep(0.5) # Anti-rate-limit basique
            
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
