import os
import re
import numpy as np
from typing import List, Dict

# Configuration (identique à train.py pour rester cohérent)
AUDIO_ROOT = "../../../@assets/0.media/audio"
TIMECODE_ROOT = "../../../@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/timecode_chroniques"
MAX_DURATION = 10.0

def parse_timecode(tc_str: str) -> float:
    """Convertit [HH:MM:SS:mmm] en secondes."""
    parts = tc_str.strip("[] ").split(":")
    if len(parts) == 4:
        h, m, s, ms = map(int, parts)
        return h * 3600 + m * 60 + s + ms / 1000.0
    return 0.0

def clean_label(label: str) -> str:
    """Nettoyage et consolidation des labels (identique à train.py)."""
    label = label.strip().replace(".mp3", "").replace(".m4a", "")
    if re.search(r"journal.*7\s*h", label, re.I): return "journal-7h"
    if re.search(r"journal.*8\s*h", label, re.I): return "journal-8h"
    if re.search(r"journal.*9\s*h", label, re.I): return "journal-9h"
    if "laurent" in label.lower() and "gerra" in label.lower(): return "laurent-gerra"
    if "edito" in label.lower() and "etienne" in label.lower(): return "edito-etienne-gernelle"
    if "vrai" in label.lower() and "faux" in label.lower(): return "le-vrai-du-faux"
    if "angle" in label.lower() and "eco" in label.lower(): return "l-angle-eco"
    if "pepite" in label.lower(): return "la-pepite"
    if "ca-va-mieux" in label.lower() or "ca-va-beaucoup-mieux" in label.lower(): return "ca-va-mieux"
    if "oeil" in label.lower() and "philippe" in label.lower(): return "oeil-philippe"
    if "rtl-evenement" in label.lower() or "rtl_evenement" in label.lower(): return "rtl-evenement"
    
    return label.replace("_", "-")

def load_dataset_pairs():
    """Charge les paires audio/timecode (identique à train.py)."""
    data = []
    if not os.path.exists(TIMECODE_ROOT):
        return []

    radios = [d for d in os.listdir(TIMECODE_ROOT) if os.path.isdir(os.path.join(TIMECODE_ROOT, d))]
    
    for radio in radios:
        news_dir = os.path.join(TIMECODE_ROOT, radio, "news")
        if not os.path.exists(news_dir):
            continue
            
        for tc_file in os.listdir(news_dir):
            if tc_file.endswith("_new_from_audio.txt"):
                date_str = tc_file.replace("_new_from_audio.txt", "")
                audio_folder = os.path.join(AUDIO_ROOT, radio, date_str)
                if not os.path.exists(audio_folder):
                    continue
                
                audio_files = os.listdir(audio_folder)
                audio_file = None
                trimmed = [f for f in audio_files if "_trimmed" in f and (f.endswith(".mp3") or f.endswith(".m4a"))]
                if trimmed:
                    audio_file = trimmed[0]
                else:
                    others = [f for f in audio_files if (f.endswith(".mp3") or f.endswith(".m4a")) and not f.endswith("_trimmed.mp3") and not f.endswith("_trimmed.m4a")]
                    if others:
                        audio_file = others[0]
                
                if audio_file:
                    data.append({
                        "radio": radio,
                        "date": date_str,
                        "audio_path": os.path.join(audio_folder, audio_file),
                        "tc_path": os.path.join(news_dir, tc_file)
                    })
    return data

def main():
    pairs = load_dataset_pairs()
    
    stats = {
        "chronicle_segments": 0,
        "background_segments": 0,
        "labels": {}
    }
    
    total_chronicle_duration = 0.0
    
    for pair in pairs:
        chronicle_intervals = []
        with open(pair['tc_path'], 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r"\[(.*?)\]\s*-\s*\[(.*?)\]\s*(.*)", line)
                if match:
                    start_str, end_str, label = match.groups()
                    start_sec = parse_timecode(start_str)
                    end_sec = parse_timecode(end_str)
                    label_name = clean_label(label)
                    
                    if end_sec <= start_sec:
                        continue
                    
                    chronicle_intervals.append((start_sec, end_sec))
                    total_chronicle_duration += (end_sec - start_sec)
                    
                    # Logique de segmentation des chroniques (train.py)
                    count = 0
                    for seg_start in np.arange(start_sec, end_sec - 2.0, 5.0):
                        seg_end = min(seg_start + MAX_DURATION, end_sec)
                        if seg_end - seg_start < 2.0: break
                        count += 1
                    
                    stats["chronicle_segments"] += count
                    stats["labels"][label_name] = stats["labels"].get(label_name, 0) + count

        # Logique de segmentation du background (train.py)
        chronicle_intervals.sort()
        last_end = 0
        for start, end in chronicle_intervals:
            if start > last_end + 10.0:
                for bg_start in np.arange(last_end, start - 10.0, 20.0):
                    stats["background_segments"] += 1
            last_end = max(last_end, end)
            
    total_segments = stats["chronicle_segments"] + stats["background_segments"]
    
    if total_segments > 0:
        pct_chronicle = (stats["chronicle_segments"] / total_segments) * 100
        pct_background = (stats["background_segments"] / total_segments) * 100
    else:
        pct_chronicle = pct_background = 0
        
    print("====================================================")
    print("   STATISTIQUES DES DONNÉES D'ENTRAÎNEMENT")
    print("====================================================")
    print(f"Nombre d'audios sources analysés : {len(pairs)}")
    print(f"Nombre total de segments générés : {total_segments}")
    print(f"  - Chroniques : {stats['chronicle_segments']} ({pct_chronicle:.2f}%)")
    print(f"  - Non-chroniques (background) : {stats['background_segments']} ({pct_background:.2f}%)")
    print("----------------------------------------------------")
    print(f"Durée totale cumulée des chroniques : {total_chronicle_duration/60:.2f} minutes")
    print("----------------------------------------------------")
    print("Détail par label de chronique (nombre de segments) :")
    
    sorted_labels = sorted(stats["labels"].items(), key=lambda x: x[1], reverse=True)
    for label, count in sorted_labels:
        print(f"  - {label:.<30} : {count}")
    print("====================================================")

if __name__ == "__main__":
    main()
