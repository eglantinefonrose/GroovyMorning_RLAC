import argparse
import json
import sys
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from transcriber import Transcriber

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = "deepseek-v4-flash"

def analyze_with_deepseek(phrase, history):
    if not DEEPSEEK_API_KEY:
        return {"detecte": False}
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = "Tu es un expert radio. Détecte si la phrase suivante est le début d'une chronique. Réponds UNIQUEMENT en JSON: {\"detecte\": true/false, \"chronique\": \"nom\"}"
    
    context_text = "\n".join([h['text'] for h in history[-5:]])
    user_content = f"CONTEXTE :\n{context_text}\n\nPHRASE :\n{phrase}"
    
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        return response.json()["choices"][0]["message"]["content"]
    except:
        return "{\"detecte\": false}"

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche DeepSeek)")
    parser.add_argument("audio", help="Chemin audio")
    parser.add_argument("--provider", default="kyutai_stt", choices=["whisper", "kyutai", "kyutai_mlx", "kyutai_stt"], help="Fournisseur de transcription")
    parser.add_argument("--whisper-model", default="base")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY:
        print("Erreur: DEEPSEEK_API_KEY non trouvée", file=sys.stderr)
        sys.exit(1)

    transcriber = Transcriber(model_size=args.whisper_model, provider=args.provider)
    results = []
    history = []
    
    print(f"Analyse avec DeepSeek {MODEL} via {args.provider}...", file=sys.stderr)
    for seg in transcriber.transcribe_stream(args.audio):
        res_raw = analyze_with_deepseek(seg['text'], history)
        try:
            res = json.loads(res_raw)
            if res.get("detecte"):
                results.append({
                    "start": round(seg['start'], 2),
                    "end": round(seg['start'] + 60.0, 2),
                    "label": res.get("chronique", "chronique"),
                    "confidence": 1.0
                })
            history.append(seg)
        except:
            pass
            
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
