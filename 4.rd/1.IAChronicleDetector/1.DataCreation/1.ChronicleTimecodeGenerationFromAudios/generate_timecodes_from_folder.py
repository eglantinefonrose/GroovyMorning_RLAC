import os
import re
import argparse
import unicodedata

def parse_time(time_str):
    """Convertit HH:MM:SS.mmm en secondes."""
    h, m, s = time_str.split(':')
    s, ms = s.split('.')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def parse_srt(filepath):
    """Parse un fichier SRT (format Whisper [HH:MM:SS.mmm --> HH:MM:SS.mmm] Texte)."""
    segments = []
    # Pattern pour le format spécifique des fichiers Whisper fournis
    pattern = re.compile(r'\[\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*\]\s+(.*)')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    start, end, text = match.groups()
                    segments.append({'start': start, 'end': end, 'text': text})
    except Exception as e:
        print(f"Erreur de lecture {filepath}: {e}")
    return segments

def normalize(text):
    """Normalise le texte : sans accents, minuscules, uniquement alphanumérique."""
    if not text:
        return ""
    # Décomposition pour séparer les accents des lettres
    text = unicodedata.normalize('NFD', text)
    # Suppression des accents et passage en minuscules
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn']).lower()
    # On ne garde que les lettres et chiffres (supprime ponctuation, espaces, retours à la ligne)
    return re.sub(r'[^a-z0-9]', '', text)

def find_segment_range(main_segments, chronicle_segments):
    """Cherche la position de la chronique dans la transcription globale."""
    if not chronicle_segments or not main_segments:
        return None, None
    
    chron_duration = parse_time(chronicle_segments[-1]['end']) - parse_time(chronicle_segments[0]['start'])
    
    # Nettoyage des segments de la chronique (on ignore les phrases trop courtes ou les fillers)
    common_fillers = {"rtlmatin", "bonjour", "merci", "radio", "franceinter", "franceinfo"}
    clean_chron = [normalize(s['text']) for s in chronicle_segments if len(normalize(s['text'])) > 15 and normalize(s['text']) not in common_fillers]
    
    if not clean_chron:
        clean_chron = [normalize(s['text']) for s in chronicle_segments if len(normalize(s['text'])) > 5]

    if not clean_chron:
        return None, None

    # Reconstruction de la transcription globale en une seule chaîne
    main_text_list = [normalize(s['text']) for s in main_segments]
    full_main_str = "".join(main_text_list)
    
    # Mapping des positions de caractères vers les timecodes
    main_char_map = []
    current_char = 0
    for s in main_segments:
        norm = normalize(s['text'])
        main_char_map.append((current_char, current_char + len(norm), s['start'], s['end']))
        current_char += len(norm)

    best_range = (None, None)
    min_diff = float('inf')

    # Recherche par "chunks" (on essaie les premières phrases de la chronique)
    for i in range(min(5, len(clean_chron))):
        start_chunk = clean_chron[i]
        # On cherche toutes les occurrences du début
        for m in re.finditer(re.escape(start_chunk), full_main_str):
            start_pos = m.start()
            # Pour chaque début, on cherche une fin correspondante (dernières phrases)
            for j in range(1, min(6, len(clean_chron) + 1)):
                end_chunk = clean_chron[-j]
                end_pos_idx = full_main_str.find(end_chunk, start_pos)
                
                if end_pos_idx != -1:
                    end_pos = end_pos_idx + len(end_chunk)
                    
                    # Conversion des positions en timecodes
                    s_time, e_time = None, None
                    for c_start, c_end, t_start, t_end in main_char_map:
                        if s_time is None and c_end > start_pos: s_time = t_start
                        if c_start < end_pos: e_time = t_end
                    
                    if s_time and e_time:
                        found_dur = parse_time(e_time) - parse_time(s_time)
                        # Validation : la durée trouvée doit être cohérente avec la chronique
                        if abs(found_dur - chron_duration) < min_diff:
                            min_diff = abs(found_dur - chron_duration)
                            best_range = (s_time, e_time)
                            
    # On valide si l'écart de durée est acceptable (max 2 min de différence)
    if min_diff < 120:
        return best_range
    return None, None

def main():
    parser = argparse.ArgumentParser(description="Génère le timecode d'une ou plusieurs chroniques dans une émission complète.")
    parser.add_argument("--main", required=True, help="Chemin vers le SRT de l'émission complète")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chronicle", help="Chemin vers un seul SRT de chronique")
    group.add_argument("--chronicles_dir", help="Chemin vers un dossier contenant plusieurs SRT de chroniques")
    parser.add_argument("--output", help="Chemin du fichier de sortie (optionnel)")

    args = parser.parse_args()

    if not os.path.exists(args.main):
        print(f"Erreur : Le fichier principal n'existe pas : {args.main}")
        return

    main_segments = parse_srt(args.main)
    main_name = os.path.basename(args.main)
    
    # Liste des fichiers à traiter
    chronicle_files = []
    if args.chronicle:
        if os.path.exists(args.chronicle):
            chronicle_files.append(args.chronicle)
        else:
            print(f"Erreur : Le fichier de chronique n'existe pas : {args.chronicle}")
            return
    elif args.chronicles_dir:
        if os.path.isdir(args.chronicles_dir):
            import glob
            chronicle_files = sorted(glob.glob(os.path.join(args.chronicles_dir, "*.srt")))
            if not chronicle_files:
                print(f"Erreur : Aucun fichier SRT trouvé dans {args.chronicles_dir}")
                return
        else:
            print(f"Erreur : Le dossier {args.chronicles_dir} n'existe pas")
            return

    results = []
    print(f"Recherche dans '{main_name}' ({len(chronicle_files)} fichier(s) à traiter)...")

    for c_path in chronicle_files:
        name = os.path.basename(c_path).replace("_transcription.srt", "").replace(".srt", "")
        chron_segments = parse_srt(c_path)
        
        start, end = find_segment_range(main_segments, chron_segments)

        if start and end:
            res_line = f"{start} - {end} : {name}"
            results.append(res_line)
            print(f" [+] Trouvé : {res_line}")
        else:
            print(f" [-] Non trouvé : {name}")

    if results:
        if args.output:
            os.makedirs(os.path.dirname(args.output), exist_ok=True) if os.path.dirname(args.output) else None
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write("\n".join(results) + "\n")
            print(f"\n{len(results)} résultat(s) enregistré(s) dans : {args.output}")
        elif not args.chronicle: # Si on est en mode dossier et pas d'output, on fait un petit récap
            print("\nSynthèse des résultats :")
            print("\n".join(results))

if __name__ == "__main__":
    main()
