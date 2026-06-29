import os
import argparse
import json
import sys
import re

# Tentative d'import d'ollama
try:
    import ollama
except ImportError:
    ollama = None

def parse_time_to_seconds(time_str):
    """
    Parse divers formats de temps vers secondes:
    - HH:MM:SS.mmm
    - MM:SS.mmm
    - HH:MM:SS,mmm
    - MM:SS,mmm
    """
    if not time_str or time_str.lower() == "inconnu":
        return 0.0
        
    time_str = time_str.replace(',', '.')
    time_str = time_str.strip()
    
    # Gestion des formats comme "00:19:03.560" ou "13:15.000"
    parts = time_str.split(':')
    
    try:
        if len(parts) == 3: # HH:MM:SS.mmm
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2: # MM:SS.mmm
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            # Peut-être juste des secondes?
            return float(time_str)
    except ValueError:
        return 0.0

def calculate_iou(range1, range2):
    start1, end1 = range1
    start2, end2 = range2
    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = (end1 - start1) + (end2 - start2) - intersection
    return intersection / union if union > 0 else 0.0

def evaluate_quality(model_name, transcription_path, gt_path):
    if ollama is None:
        print("Erreur : La bibliothèque 'ollama' n'est pas installée. Installez-la avec 'pip install ollama'.")
        return

    # 1. Charger la transcription
    if not os.path.exists(transcription_path):
        print(f"Erreur : Le fichier de transcription '{transcription_path}' n'existe pas.")
        return
        
    with open(transcription_path, 'r', encoding='utf-8') as f:
        transcription_content = f.read()

    # 2. Préparer le prompt pour Ollama
    system_prompt = "Tu es un expert en analyse de transcriptions radio. Ton rôle est de détecter les chroniques et de renvoyer les timecodes au format JSON uniquement."
    
    user_prompt = f"""
Analyse la transcription suivante et extrais les chroniques détectées.
Pour chaque chronique, indique le nom, le timecode de début et le timecode de fin.

Format JSON attendu :
{{
  "chroniques": [
    {{
      "nom": "Nom de la chronique",
      "debut": "HH:MM:SS.mmm",
      "fin": "HH:MM:SS.mmm"
    }}
  ]
}}

Transcription :
{transcription_content[:50000]}
"""

    print(f"--- Évaluation du modèle LLM '{model_name}' ---")
    print(f"Transcription: {transcription_path}")
    print(f"Ground Truth: {gt_path}")
    print(f"\n🔍 Appel à Ollama (modèle: {model_name})...")

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format="json"
        )
        data = json.loads(response['message']['content'])
    except Exception as e:
        print(f"Erreur lors de l'appel à Ollama ou du parsing JSON : {e}")
        return

    print(f"\n📺 Chroniques détectées par {model_name} :")
    print("-" * 60)
    print(f"{'Nom de la chronique':<35} | {'Début':<10} | {'Fin':<10}")
    print("-" * 60)
    pred_intervals = []
    for ch in data.get("chroniques", []):
        try:
            nom = ch.get("nom", "Inconnu")
            debut_str = ch.get("debut", "0")
            fin_str = ch.get("fin", "0")
            
            print(f"{nom[:35]:<35} | {debut_str:<10} | {fin_str:<10}")
            
            start = parse_time_to_seconds(debut_str)
            end = parse_time_to_seconds(fin_str)
            if end > start:
                pred_intervals.append((start, end))
        except:
            continue
    print("-" * 60)

    # 3. Charger la vérité terrain
    if not os.path.exists(gt_path):
        print(f"Erreur : Le fichier ground truth '{gt_path}' n'existe pas.")
        return

    gt_intervals = []
    with open(gt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            # On gère les formats HH:MM:SS.mmm - HH:MM:SS.mmm
            # ou HH:MM:SS.mmm | HH:MM:SS.mmm
            parts = re.split(r'[-|]', line)
            if len(parts) >= 2:
                try:
                    s_str = parts[0].replace('-->', '').strip()
                    e_str = parts[1].strip()
                    start = parse_time_to_seconds(s_str)
                    end = parse_time_to_seconds(e_str)
                    if end > start:
                        gt_intervals.append((start, end))
                except:
                    continue

    if not gt_intervals:
        print("Erreur : Aucun intervalle trouvé dans le fichier ground truth.")
        return

    # 4. Calculer les métriques
    n_gt = len(gt_intervals)
    n_pred = len(pred_intervals)
    
    # Score de cardinalité (40%)
    cardinality_score = max(0.0, 1.0 - abs(n_gt - n_pred) / n_gt) if n_gt > 0 else (1.0 if n_pred == 0 else 0.0)
    
    chronicle_scores = []
    pred_used = set()
    max_offset_tolerance = 60.0

    for gt in gt_intervals:
        best_iou = -1
        best_p_idx = -1
        for p_idx, p in enumerate(pred_intervals):
            if p_idx in pred_used: continue
            iou = calculate_iou(p, gt)
            if iou > best_iou:
                best_iou = iou
                best_p_idx = p_idx
        
        if best_p_idx != -1 and best_iou > 0:
            pred_used.add(best_p_idx)
            p = pred_intervals[best_p_idx]
            offset = (abs(p[0] - gt[0]) + abs(p[1] - gt[1])) / 2
            ch_score = max(0.0, 1.0 - (offset / max_offset_tolerance))
            chronicle_scores.append(ch_score)
        else:
            chronicle_scores.append(0.0)

    alignment_score = sum(chronicle_scores) / len(chronicle_scores) if chronicle_scores else 0.0
    
    # Note finale (40/60)
    global_score = (cardinality_score * 0.4) + (alignment_score * 0.6)

    print("\n" + "="*40)
    print(f"📊 NOTE DE QUALITÉ FINALE : {global_score*100:.1f}/100")
    print("="*40)
    print(f"- Modèle : {model_name}")
    print(f"- Chroniques : {n_pred} détectées / {n_gt} attendues")
    print(f"- Cardinalité (40%) : {cardinality_score*100:.1f}%")
    print(f"- Alignement Temporel (60%) : {alignment_score*100:.1f}%")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Évalue la qualité de détection des chroniques par un LLM.")
    parser.add_argument("model", help="Nom du modèle Ollama à évaluer")
    parser.add_argument("transcription", help="Chemin vers le fichier de transcription (SRT ou TXT)")
    parser.add_argument("gt", help="Chemin vers le fichier de vérité terrain (timecodes)")
    
    args = parser.parse_args()
    evaluate_quality(args.model, args.transcription, args.gt)
