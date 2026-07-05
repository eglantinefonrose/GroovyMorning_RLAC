import argparse
import json
import sys
import os
import ollama
from pathlib import Path
from faster_whisper import WhisperModel

MODEL = "mistral"

def transcribe_audio(audio_path, model_size="base"):
    print(f"Transcription de {audio_path}...", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, beam_size=5, language="fr")
    
    # Formatage SRT-like pour le prompt attendu par cette approche
    srt_content = ""
    for i, s in enumerate(segments, 1):
        start = format_timestamp(s.start)
        end = format_timestamp(s.end)
        srt_content += f"{i}\n{start} --> {end}\n{s.text.strip()}\n\n"
    return srt_content

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def main():
    parser = argparse.ArgumentParser(description="Détecte les chroniques (Approche LLM Global)")
    parser.add_argument("audio", help="Chemin audio")
    parser.add_argument("--whisper-model", default="base")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        sys.exit(1)

    transcription = transcribe_audio(args.audio, model_size=args.whisper_model)
    
    with open('prompt.txt', 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    full_prompt = prompt_template.replace("[TRANSCRIPTION]", transcription)
    
    print(f"Appel à Ollama ({MODEL})...", file=sys.stderr)
    try:
        response = ollama.chat(model=MODEL, messages=[
            {'role': 'user', 'content': full_prompt}
        ])
        content = response['message']['content']
        
        # Extraction du JSON de la réponse (souvent entouré de ```json ... ```)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        # On suppose que la réponse est une liste de chroniques
        print(content)
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        print("[]")

if __name__ == "__main__":
    main()
