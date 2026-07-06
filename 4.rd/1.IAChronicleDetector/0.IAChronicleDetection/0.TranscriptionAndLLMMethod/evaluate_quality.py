import os
import argparse
import json
import sys
import time
import subprocess
import re
import ollama
from pathlib import Path
from faster_whisper import WhisperModel

MODEL_LLM = "mistral"
WHISPER_MODEL_SIZE = "base"
STEP_SEC = 60  # Intervalle de simulation (secondes)

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def parse_timecode(tc):
    """Convertit HH:MM:SS ou MM:SS en secondes."""
    parts = tc.replace(',', '.').split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(tc)

def extract_audio_chunk(input_path, end_time, output_path):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", str(end_time),
        "-c", "copy", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def call_llm(srt_text):
    prompt = f"""
Analyse cette transcription SRT et identifie les chroniques radio.
Pour chaque chronique, donne le nom et le timecode de début.

Transcription :
{srt_text}

Réponds uniquement en JSON (liste d'objets) :
[
  {{"nom": "Nom de la chronique", "debut": "HH:MM:SS"}},
  ...
]
"""
    try:
        response = ollama.chat(model=MODEL_LLM, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content']
        # Extraction basique du JSON
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Erreur LLM : {e}")
    return []

def evaluate_quality_live(audio_path, gt_path=None, acceleration=1.0):
    print(f"--- Évaluation LIVE (Transcription + LLM) ---")
    print(f"Fichier : {audio_path}")
    if gt_path:
        print(f"GT : {gt_path}")
    else:
        print("GT : Non fourni (mode détection seule)")
    
    # Chargement Ground Truth
    gt_chronicles = []
    if gt_path and os.path.exists(gt_path):
        with open(gt_path, 'r') as f:
            for line in f:
                # Format supposé : "00:12:30 - 00:15:00 Nom" ou "12:30-15:00"
                m = re.search(r'(\d+[:\.]\d+[:\.]?\d*)\s*-\s*(\d+[:\.]\d+[:\.]?\d*)', line)
                if m:
                    gt_chronicles.append({
                        'start': parse_timecode(m.group(1)),
                        'end': parse_timecode(m.group(2)),
                        'found': False
                    })
    
    whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    temp_chunk = "temp_eval_live.wav"
    
    start_wall_time = time.time()
    sim_time = 0
    all_detections = []
    
    try:
        while True:
            elapsed_wall = time.time() - start_wall_time
            target_sim_time = elapsed_wall * acceleration
            
            if target_sim_time < sim_time + STEP_SEC:
                time.sleep(0.5)
                continue
            
            sim_time += STEP_SEC
            print(f"\n[T={int(sim_time)}s] Simulation du flux...")
            
            # 1. Transcription "Live"
            extract_audio_chunk(audio_path, sim_time, temp_chunk)
            segments, info = whisper.transcribe(temp_chunk, beam_size=5, language="fr")
            
            current_srt = ""
            for i, s in enumerate(segments, 1):
                current_srt += f"{i}\n{format_timestamp(s.start)} --> {format_timestamp(s.end)}\n{s.text.strip()}\n\n"
            
            # 2. Analyse LLM
            detections = call_llm(current_srt)
            
            # 3. Comparaison avec GT et calcul latence
            for det in detections:
                det_start = parse_timecode(det['debut'])
                # Fin de la chronique (optionnelle dans le JSON du LLM, sinon on met start + 1s par défaut)
                det_end = parse_timecode(det.get('fin', det['debut']))
                if det_end <= det_start:
                    det_end = det_start + 60.0 # Valeur par défaut
                
                # Vérifier si c'est une nouvelle détection
                is_new = True
                for prev in all_detections:
                    if abs(prev['start'] - det_start) < 20: # Seuil pour considérer que c'est la même
                        is_new = False
                        break
                
                if is_new:
                    detection_entry = {
                        "label": det['nom'],
                        "start": det_start,
                        "end": det_end,
                        "detected_at": sim_time,
                        "confidence": 0.9 # Valeur arbitraire pour l'exemple
                    }
                    all_detections.append(detection_entry)
                    print(f"✨ Nouvelle chronique détectée : {det['nom']} à {det['debut']} (Sim Time: {sim_time}s)")
                    
                    # Calcul latence par rapport au GT
                    if gt_chronicles:
                        for gt in gt_chronicles:
                            if not gt['found'] and abs(gt['start'] - det_start) < 30:
                                gt['found'] = True
                                latency = sim_time - gt['start']
                                print(f"✅ Match GT! Latence : {latency:.1f}s")
                                break

            if sim_time >= info.duration:
                break
                
    finally:
        if os.path.exists(temp_chunk):
            os.remove(temp_chunk)

    # Sauvegarde du JSON
    output_json = "detections_live.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_detections, f, indent=2, ensure_ascii=False)

    print(f"\n--- Fin de la simulation ---")
    print(f"Résultats sauvegardés dans : {output_json}")
    if gt_chronicles:
        tp = sum(1 for gt in gt_chronicles if gt['found'])
        print(f"Chroniques trouvées : {tp}/{len(gt_chronicles)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("--gt", required=False, default=None)
    parser.add_argument("--acceleration", type=float, default=1.0)
    args = parser.parse_args()
    
    evaluate_quality_live(args.audio, args.gt, args.acceleration)
