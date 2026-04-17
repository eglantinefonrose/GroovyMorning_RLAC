import re
import os
from datetime import timedelta
from typing import List, Tuple, Dict
import numpy as np

def parse_timecode_to_seconds(timecode_str: str) -> float:
    """Convertit HH:MM:SS.mmm en secondes."""
    match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})', timecode_str)
    if not match:
        match = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', timecode_str)
        if not match: return 0.0
        h, m, s = match.groups()
        ms = 0
    else:
        h, m, s, ms = match.groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def load_timecodes(filepath: str) -> List[Tuple[float, float]]:
    """Extrait les paires de timecodes du fichier texte."""
    timecodes = []
    if not os.path.exists(filepath): return []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # Cherche tous les groupes de chiffres type timecode dans la ligne
            matches = re.findall(r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3})', line)
            if len(matches) >= 2:
                timecodes.append((parse_timecode_to_seconds(matches[0]), parse_timecode_to_seconds(matches[1])))
    return timecodes

def load_transcription(filepath: str) -> List[Dict]:
    """Charge le format [00:00:00.000 --> 00:00:01.000] Texte."""
    if not os.path.exists(filepath): return []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Regex ultra-flexible pour capturer [TC --> TC] ou TC --> TC suivi du texte
    pattern = re.compile(r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\]?\s*(.*?)(?=\[?\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->|$)', re.DOTALL)
    matches = pattern.finditer(content)
    
    result = []
    for m in matches:
        text = m.group(3).strip()
        # Nettoyage des éventuels index numériques en début de ligne
        text = re.sub(r'^\d+[\r\n]+', '', text).replace('\n', ' ').strip()
        result.append({
            'start': parse_timecode_to_seconds(m.group(1)),
            'end': parse_timecode_to_seconds(m.group(2)),
            'text': text
        })
    return result

def label_segments(segments: List[Dict], tc_list: List[Tuple[float, float]]) -> List[int]:
    labels = []
    for seg in segments:
        mid = (seg['start'] + seg['end']) / 2
        label = 0
        for start, end in tc_list:
            if start <= mid <= end:
                label = 1
                break
        labels.append(label)
    return labels

def extract_features(idx: int, all_segments: List[Dict]) -> Dict:
    seg = all_segments[idx]
    text = seg['text'].upper()
    
    # Caractéristiques temporelles et structurelles
    has_jingle_prev = 1 if idx > 0 and '[JINGLE]' in all_segments[idx-1]['text'].upper() else 0
    has_jingle_now = 1 if '[JINGLE]' in text else 0
    duration = seg['end'] - seg['start']
    
    total_dur = all_segments[-1]['end'] if all_segments else 3600
    rel_pos = seg['start'] / total_dur

    features = {
        'rel_pos': rel_pos,
        'duration': duration,
        'has_jingle_now': has_jingle_now,
        'has_jingle_prev': has_jingle_prev,
        'is_very_short': 1 if duration < 1.5 else 0,
        'char_count': len(seg['text']),
    }
    
    for kw in ['JOURNAL', 'METEO', 'INVITÉ', 'CHRONIQUE', 'BILLET', 'DIRECT', 'REDACTION', '7H', '8H', 'BONJOUR', 'INTER']:
        features[f'kw_{kw.lower()}'] = 1 if kw in text else 0
    return features

def format_timecode(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
