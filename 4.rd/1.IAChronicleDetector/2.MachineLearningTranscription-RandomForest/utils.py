import re
from datetime import timedelta
from typing import List, Tuple, Dict
import numpy as np


def parse_timecode_to_timedelta(time_str: str) -> timedelta:
    """Convertit un temps (HH:MM:SS,mmm ou HH:MM:SS.mmm) en timedelta"""
    time_str = time_str.replace(',', '.') # Gérer virgule ou point
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return timedelta(hours=int(h), minutes=int(m), seconds=float(s))
    return timedelta(0)


def parse_timecode(timecode_str: str) -> float:
    """Convertit un timecode MM:SS.ms en secondes (fichiers config)"""
    parts = timecode_str.replace(',', '.').split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(parts[0])


def parse_timecode_range(timecode_range: str) -> Tuple[float, float]:
    if ' - ' in timecode_range:
        parts = timecode_range.strip().split(' - ')
    elif '-' in timecode_range:
        parts = timecode_range.strip().split('-')
    else:
        raise ValueError(f"Format invalide : {timecode_range}")
    return parse_timecode(parts[0].strip()), parse_timecode(parts[1].strip())


def load_timecodes(filepath: str) -> List[Tuple[float, float]]:
    timecodes = []
    content = ""
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    if not content: return []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        try:
            timecodes.append(parse_timecode_range(line))
        except: continue
    return timecodes


def load_transcription(filepath: str) -> List[Dict]:
    """Charge une transcription de manière agnostique (SRT, VTT, Log Whisper)"""
    content = ""
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    if not content: return []

    # 1. Nettoyage préliminaire : enlever les index avec crochets [5] qui perturbent
    # content = re.sub(r'^\d+\s+\[\d{2}:\d{2}:\d{2}\]', r'\1', content, flags=re.MULTILINE)

    # 2. REGEX UNIVERSELLE
    # Cherche : [? Timecode ]? --> [? Timecode ]? (Texte)
    # Groupes : 1=Start, 2=End, 3=Texte
    pattern = re.compile(
        r'\[?(\d{1,2}:\d{2}:\d{2}[,. ]\d{3})\]?\s*-->\s*\[?(\d{1,2}:\d{2}:\d{2}[,. ]\d{3})\]?\s*(.*?)(?=\[?\d{1,2}:\d{2}:\d{2}|$)',
        re.DOTALL | re.MULTILINE
    )

    matches = list(pattern.finditer(content))
    result = []
    
    for i, match in enumerate(matches, 1):
        start_str = match.group(1).strip()
        end_str = match.group(2).strip()
        text = match.group(3).strip()
        
        # Nettoyage du texte : enlever les index résiduels ou sauts de ligne
        text = re.sub(r'^\d+[\r\n]+', '', text)
        text = text.replace('\n', ' ').strip()
        
        try:
            start_td = parse_timecode_to_timedelta(start_str)
            end_td = parse_timecode_to_timedelta(end_str)
            
            result.append({
                'index': i,
                'start': start_td.total_seconds(),
                'end': end_td.total_seconds(),
                'text': text
            })
        except Exception as e:
            continue

    if not result:
        print(f"Attention: Aucun segment trouvé dans {filepath}.")
        print(f"Echantillon du contenu : {repr(content[:100])}")
        
    return result


def label_segments(segments: List[Dict], chronique_timecodes: List[Tuple[float, float]]) -> List[int]:
    labels = []
    last_chronique_id = -1
    for segment in segments:
        seg_start, seg_end = segment['start'], segment['end']
        label = 0
        for i, (ch_start, ch_end) in enumerate(chronique_timecodes):
            if (seg_start >= ch_start and seg_start < ch_end) or (seg_end > ch_start and seg_end <= ch_end) or (seg_start <= ch_start and seg_end >= ch_end):
                if i != last_chronique_id:
                    label = 1
                    last_chronique_id = i
                else:
                    label = 2
                break
        if label == 0:
            last_chronique_id = -1
        labels.append(label)
    return labels


def extract_time_feature(text: str) -> float:
    # On cherche le format HH:MM:SS ou [HH:MM:SS]
    match = re.search(r'(\d{2}):(\d{2}):(\d{2})', text)
    if match:
        h, m, s = map(int, match.groups())
        return h * 3600 + m * 60 + s
    return 0.0


def extract_features_from_text(text: str) -> Dict:
    has_jingle = 1 if '[JINGLE]' in text.upper() else 0
    # On nettoie les crochets pour les stats mais on garde le texte
    clean_text = re.sub(r'\[.*?\]', '', text).strip()
    words = clean_text.split()
    return {
        'word_count': len(words),
        'char_count': len(clean_text),
        'has_punctuation': 1 if any(p in clean_text for p in '.!?;:') else 0,
        'has_question_mark': 1 if '?' in clean_text else 0,
        'has_exclamation': 1 if '!' in clean_text else 0,
        'avg_word_length': np.mean([len(w) for w in words]) if words else 0,
        'time_of_day': extract_time_feature(text),
        'has_jingle': has_jingle
    }


def format_timecode(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    minutes, secs = total_seconds // 60, total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def save_predictions(chroniques: List[Tuple[float, float]], output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        for start, end in chroniques:
            f.write(f"{format_timecode(start)} - {format_timecode(end)}\n")
    print(f"Prédictions sauvegardées dans {output_path}")
