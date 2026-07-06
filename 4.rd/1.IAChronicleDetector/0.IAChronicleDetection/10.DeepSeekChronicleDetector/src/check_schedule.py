import re
import sys
from datetime import datetime, timedelta

# Configuration du planning théorique (nom -> heure HH:MM)
THEORETICAL_SCHEDULE = {
    "le journal de 7h": "07:00",
    "les 80 secondes": "07:12",
    "le grand reportage": "07:15",
    "l'édito média": "07:23",
    "musicaline": "07:26",
    "le journal de 7h30": "07:30",
    "l'édito politique": "07:43",
    "l'édito éco": "07:47",
    "l'invité de 7h50": "07:50",
    "le billet de bertrand chameroy": "07:57",
    "le journal de 8h": "08:00",
    "géopolitique": "08:12",
    "l'invité de 8h20": "08:20",
    "la revue de presse": "08:47",
    "un monde nouveau": "08:52",
    "le billet de mosimann": "08:55",
    "le journal de 9h": "09:00",
}

# Points d'ancrage basés sur l'analyse de full_show_transcription.txt
# (index_phrase -> heure HH:MM)
ANCHORS = {
    1: "07:12",   # Début avec 80 secondes
    15: "07:16",  # Mention explicite "7h16"
    291: "08:00", # "L'heure du grand journal"
    807: "08:48", # Mention explicite "8h48"
    931: "09:05", # Fin estimée
}

def time_to_minutes(t_str):
    try:
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
    except:
        return 0

def minutes_to_time(minutes):
    h = int(minutes // 60) % 24
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"

def estimate_time(phrase_idx):
    """Estime l'heure d'une phrase par interpolation linéaire entre les ancres."""
    sorted_anchors = sorted(ANCHORS.items())
    
    if phrase_idx <= sorted_anchors[0][0]:
        return sorted_anchors[0][1]
    
    if phrase_idx >= sorted_anchors[-1][0]:
        return sorted_anchors[-1][1]
    
    for i in range(len(sorted_anchors) - 1):
        idx1, t1_str = sorted_anchors[i]
        idx2, t2_str = sorted_anchors[i+1]
        
        if idx1 <= phrase_idx <= idx2:
            t1 = time_to_minutes(t1_str)
            t2 = time_to_minutes(t2_str)
            
            ratio = (phrase_idx - idx1) / (idx2 - idx1)
            t_est = t1 + ratio * (t2 - t1)
            return minutes_to_time(t_est)
            
    return "??:??"

def parse_deepseek_output(text):
    """Extrait les détections d'un log DeepSeek."""
    detections = []
    # On split par [DÉTECTION] mais on garde le contenu
    parts = re.split(r'(\[DÉTECTION\])', text)
    
    current_phrase_num = None
    
    # Parcourir les parties pour associer détection et numéro de phrase
    for i in range(len(parts)):
        if parts[i] == "[DÉTECTION]":
            block = parts[i+1] if i+1 < len(parts) else ""
            
            chronique_match = re.search(r'🔔 Chronique trouvée\s*:\s*(.*)', block)
            phrase_content_match = re.search(r'Phrase\s*:\s*"(.*)"', block)
            
            # Chercher le numéro de phrase dans le bloc ou juste après
            phrase_num_match = re.search(r'Traitement phrase (\d+)/', block)
            if not phrase_num_match:
                # Chercher dans la partie suivante du texte
                next_text = parts[i+2] if i+2 < len(parts) else ""
                phrase_num_match = re.search(r'Traitement phrase (\d+)/', next_text)
            
            if chronique_match:
                chronique = chronique_match.group(1).strip().lower()
                # On nettoie le nom de la chronique (enlever émojis, etc.)
                chronique = re.sub(r'[^\w\s\']', '', chronique).strip()
                
                phrase_num = int(phrase_num_match.group(1)) if phrase_num_match else None
                
                detections.append({
                    "chronique": chronique,
                    "phrase_idx": phrase_num,
                    "phrase_text": phrase_content_match.group(1) if phrase_content_match else ""
                })
            
    return detections

def compare_with_schedule(detections):
    print(f"\n{'CHRONIQUE':<25} | {'PHRASE':<6} | {'ESTIMÉE':<8} | {'THÉORIQUE':<9} | {'ÉCART':<8} | {'STATUT'}")
    print("-" * 85)
    
    results = {"VALIDÉ": 0, "REJETÉ (TROP TÔT)": 0, "REJETÉ (DÉJÀ PASSÉ)": 0, "HORS GRILLE": 0}
    validated_chroniques = set()
    validated_list = []
    last_theo_minutes = -1

    for det in detections:
        name = det['chronique']
        idx = det['phrase_idx']
        est_time = estimate_time(idx) if idx else "??:??"
        est_minutes = time_to_minutes(est_time)
        
        # Match flou pour le nom de la chronique (on trie par longueur décroissante pour éviter les sous-chaînes)
        theo_time = None
        best_match_key = None
        for k in sorted(THEORETICAL_SCHEDULE.keys(), key=len, reverse=True):
            if k in name or name in k:
                theo_time = THEORETICAL_SCHEDULE[k]
                best_match_key = k
                break
        
        status = "INCONNU"
        diff_str = "-"
        
        if theo_time:
            theo_minutes = time_to_minutes(theo_time)
            diff = est_minutes - theo_minutes
            diff_str = f"{diff:+} min"
            
            # RÈGLE 1 : Trop tôt (> 1 min avant l'horaire théorique)
            if diff < -1:
                status = "REJETÉ (TROP TÔT)"
                results["REJETÉ (TROP TÔT)"] += 1
            
            # RÈGLE 2 : Déjà validée (doublon)
            elif best_match_key in validated_chroniques:
                status = "REJETÉ (DÉJÀ PASSÉ)"
                results["REJETÉ (DÉJÀ PASSÉ)"] += 1
            
            # RÈGLE 3 : Ordre chronologique de la grille (ne peut pas revenir en arrière)
            elif theo_minutes < last_theo_minutes:
                status = "REJETÉ (HORS ORDRE)"
                # On peut considérer ça comme "déjà passé" dans le sens où la grille a avancé
                results["REJETÉ (DÉJÀ PASSÉ)"] += 1
            
            else:
                status = "VALIDÉ"
                validated_chroniques.add(best_match_key)
                validated_list.append({
                    "name": best_match_key,
                    "time": est_time,
                    "diff": diff_str
                })
                last_theo_minutes = theo_minutes
                results["VALIDÉ"] += 1
        else:
            status = "HORS GRILLE"
            theo_time = "-"
            results["HORS GRILLE"] += 1
            
        print(f"{name[:25]:<25} | {str(idx):<6} | {est_time:<8} | {theo_time:<9} | {diff_str:<8} | {status}")

    print("-" * 85)
    print(f"RÉSUMÉ : {results['VALIDÉ']} Validés, {results['REJETÉ (TROP TÔT)']} Trop tôt, {results['REJETÉ (DÉJÀ PASSÉ)']} Déjà passés/Hors ordre")

    if validated_list:
        print("\n" + "="*50)
        print("   TABLEAU FINAL DES CHRONIQUES VALIDÉES")
        print("="*50)
        print(f"{'CHRONIQUE':<25} | {'HEURE':<8} | {'ÉCART'}")
        print("-" * 50)
        for v in validated_list:
            print(f"{v['name'][:25]:<25} | {v['time']:<8} | {v['diff']}")
        print("="*50)
    else:
        print("\nAucune chronique n'a été validée.")

def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
    else:
        print("Veuillez fournir un fichier de log ou coller le texte (Ctrl+D pour terminer) :")
        content = sys.stdin.read()
        
    detections = parse_deepseek_output(content)
    if not detections:
        print("Aucune détection trouvée dans l'input.")
        return
        
    compare_with_schedule(detections)

if __name__ == "__main__":
    main()
