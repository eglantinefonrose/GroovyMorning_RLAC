import srt
import re
from datetime import timedelta
from typing import List, Tuple, Dict
import numpy as np


def parse_timecode(timecode_str: str) -> float:
    """Convertit un timecode MM:SS.ms en secondes"""
    parts = timecode_str.replace(',', '.').split(':')
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        return float(parts[0])


def parse_timecode_range(timecode_range: str) -> Tuple[float, float]:
    """Parse une ligne de timecode 'start - end' ou 'start-end'"""
    # Gérer différents séparateurs possibles
    if ' - ' in timecode_range:
        parts = timecode_range.strip().split(' - ')
    elif '-' in timecode_range:
        parts = timecode_range.strip().split('-')
    else:
        raise ValueError(f"Format de ligne invalide (séparateur '-' manquant) : {timecode_range}")
    
    if len(parts) < 2:
        raise ValueError(f"Format de ligne incomplet : {timecode_range}")
        
    return parse_timecode(parts[0].strip()), parse_timecode(parts[1].strip())


def load_timecodes(filepath: str) -> List[Tuple[float, float]]:
    """Charge les timecodes depuis un fichier avec gestion d'erreurs"""
    timecodes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'): # Ignorer lignes vides et commentaires
                continue
            try:
                start, end = parse_timecode_range(line)
                timecodes.append((start, end))
            except Exception as e:
                print(f"Attention: Ligne {i} ignorée dans {filepath} : {e}")
    return timecodes


def load_transcription(filepath: str) -> List[Dict]:
    """Charge une transcription SRT et gère les index modifiés [HH:MM:SS]"""
    with open(filepath, 'r', encoding='utf-8') as f:
        srt_content = f.read()

    # 1. Extraire les heures réelles associées aux index (ex: "5 [07:00:19]")
    # On crée un dictionnaire index -> heure
    time_map = {}
    for match in re.finditer(r'^(\d+)\s+\[(\d{2}:\d{2}:\d{2})\]', srt_content, re.MULTILINE):
        idx = int(match.group(1))
        time_str = match.group(2)
        time_map[idx] = time_str

    # 2. Nettoyer le contenu pour qu'il soit au format SRT standard (juste l'index)
    # pour que la lib srt puisse le parser sans erreur
    clean_content = re.sub(r'^(\d+)\s+\[\d{2}:\d{2}:\d{2}\]', r'\1', srt_content, flags=re.MULTILINE)

    try:
        segments = list(srt.parse(clean_content))
    except srt.SRTParseError as e:
        print(f"Erreur de parsing SRT dans {filepath}: {e}")
        return []

    result = []
    for seg in segments:
        text = seg.content.replace('\n', ' ')
        
        # 3. Ré-injecter l'heure dans le texte si elle était dans l'index
        # Cela permet à extract_features_from_text de la trouver
        if seg.index in time_map:
            text = f"[{time_map[seg.index]}] {text}"
            
        result.append({
            'index': seg.index,
            'start': seg.start.total_seconds(),
            'end': seg.end.total_seconds(),
            'text': text
        })

    return result


def label_segments(segments: List[Dict], chronique_timecodes: List[Tuple[float, float]]) -> List[int]:
    """
    Labelise chaque segment avec 3 classes :
    0: Hors chronique
    1: DEBUT de chronique (premier segment d'un bloc)
    2: DANS la chronique (segments suivants)
    """
    labels = []
    last_chronique_id = -1

    for segment in segments:
        seg_start = segment['start']
        seg_end = segment['end']
        label = 0

        for i, (ch_start, ch_end) in enumerate(chronique_timecodes):
            # Vérifier le chevauchement
            if (seg_start >= ch_start and seg_start < ch_end) or \
               (seg_end > ch_start and seg_end <= ch_end) or \
               (seg_start <= ch_start and seg_end >= ch_end):
                
                if i != last_chronique_id:
                    label = 1  # C'est une nouvelle chronique
                    last_chronique_id = i
                else:
                    label = 2  # C'est la suite de la même chronique
                break
        
        if label == 0:
            last_chronique_id = -1
            
        labels.append(label)

    return labels


def extract_time_feature(text: str) -> float:
    """Extraie l'heure du marqueur [HH:MM:SS] et convertit en secondes depuis minuit"""
    match = re.search(r'\[(\d{2}):(\d{2}):(\d{2})\]', text)
    if match:
        h, m, s = map(int, match.groups())
        return h * 3600 + m * 60 + s
    return 0.0


def extract_features_from_text(text: str) -> Dict:
    """Extrait des features basiques du texte"""
    # Détection des jingles avant nettoyage
    has_jingle = 1 if '[JINGLE]' in text.upper() else 0
    
    # Nettoyer les marqueurs pour les stats de texte
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
    """Convertit des secondes en format MM:SS"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def save_predictions(chroniques: List[Tuple[float, float]], output_path: str):
    """Sauvegarde les chroniques détectées dans un fichier"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for start, end in chroniques:
            f.write(f"{format_timecode(start)} - {format_timecode(end)}\n")
    print(f"Prédictions sauvegardées dans {output_path}")