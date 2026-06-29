import re
import os
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
    """Convertit un temps (HH:MM:SS.ms ou MM:SS.ms) en secondes"""
    # Nettoyage : enlever les crochets, espaces, etc.
    timecode_str = timecode_str.strip(' []\r\n\t')
    timecode_str = timecode_str.replace(',', '.') # Gérer virgule ou point
    
    parts = timecode_str.split(':')
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        elif len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return 0.0
    return 0.0


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
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                break
        except (UnicodeDecodeError, FileNotFoundError):
            continue
            
    if not content:
        return []
        
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        try:
            tc_range = parse_timecode_range(line)
            timecodes.append(tc_range)
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


def calculate_quality_score(predictions: List[Tuple[float, float]], 
                            ground_truth: List[Tuple[float, float]], 
                            processing_time: float = 0,
                            audio_duration: float = 3600) -> Dict:
    """
    Calcule une note de qualité sur 100 points.
    1. Précision Temporelle (30 pts)
    2. Fiabilité de Détection (40 pts) - F1 Score
    3. Expérience Utilisateur (20 pts)
    4. Efficacité Technique (10 pts)
    """
    if not ground_truth:
        return {"total_score": 0, "details": "No ground truth provided"}
    
    # 1. Fiabilité de Détection (40 pts)
    # Calcul simple du F1 basé sur le recouvrement temporel
    tp = 0.0
    fp = 0.0
    fn = 0.0
    
    # On discrétise le temps par pas de 1s pour simplifier
    max_time = int(max(max([e for s, e in ground_truth]), max([e for s, e in predictions] or [0])) + 1)
    gt_mask = np.zeros(max_time)
    pr_mask = np.zeros(max_time)
    
    for s, e in ground_truth:
        gt_mask[int(s):int(e)] = 1
    for s, e in predictions:
        pr_mask[int(s):int(e)] = 1
        
    intersection = np.sum(np.logical_and(gt_mask, pr_mask))
    precision = intersection / np.sum(pr_mask) if np.sum(pr_mask) > 0 else 0
    recall = intersection / np.sum(gt_mask) if np.sum(gt_mask) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    score_reliability = f1 * 40

    # 2. Précision Temporelle (30 pts)
    # MAE sur les bornes des segments correspondants
    errors = []
    for gt_s, gt_e in ground_truth:
        # Trouver la prédiction la plus proche
        best_err = 999.0
        for pr_s, pr_e in predictions:
            err = abs(gt_s - pr_s) + abs(gt_e - pr_e)
            if err < best_err:
                best_err = err
        if best_err != 999.0:
            errors.append(best_err)
    
    mae = np.mean(errors) if errors else 10.0
    score_precision = max(0, 30 * (1 - mae / 10.0)) # 0 pts si > 10s d'erreur totale

    # 3. Expérience Utilisateur (20 pts)
    # Pénalité pour les micro-segments ou les coupures trop nombreuses
    num_predictions = len(predictions)
    num_gt = len(ground_truth)
    diff_segments = abs(num_predictions - num_gt)
    score_ux = max(0, 20 - (diff_segments * 4))

    # 4. Efficacité Technique (10 pts)
    # Si processing_time / audio_duration < 0.1 (10x plus vite que le temps réel)
    if processing_time > 0 and audio_duration > 0:
        ratio = processing_time / audio_duration
        score_efficiency = max(0, 10 * (1 - ratio * 2)) # 0 pts si > 50% du temps réel
    else:
        score_efficiency = 5 # Score par défaut si non mesuré

    total_score = score_reliability + score_precision + score_ux + score_efficiency
    
    return {
        "total_score": round(total_score, 1),
        "details": {
            "reliability_f1": round(score_reliability, 1),
            "temporal_precision": round(score_precision, 1),
            "user_experience": round(score_ux, 1),
            "technical_efficiency": round(score_efficiency, 1),
            "f1_value": round(f1, 3),
            "mae_seconds": round(mae, 2)
        }
    }
