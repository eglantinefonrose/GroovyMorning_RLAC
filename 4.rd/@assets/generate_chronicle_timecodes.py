import os
import re
import glob

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

import unicodedata

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
    input_dir = "1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo"
    output_dir = "2.humanOutputs/1.timecode-segments/1.automatic-from-chronique-transcription"
    os.makedirs(output_dir, exist_ok=True)

    print("Démarrage de la recherche de timecodes...")
    
    for root, dirs, files in os.walk(input_dir):
        if 'chroniques' in dirs:
            chron_path = os.path.join(root, 'chroniques')
            main_srt = [f for f in files if f.endswith('.srt')]
            if not main_srt: continue
            
            # Le fichier principal est le plus gros SRT du dossier
            main_file = os.path.join(root, sorted(main_srt, key=lambda x: os.path.getsize(os.path.join(root, x)), reverse=True)[0])
            main_segments = parse_srt(main_file)
            
            results = []
            not_found = []
            for c_file in sorted(glob.glob(os.path.join(chron_path, "*.srt"))):
                name = os.path.basename(c_file).replace("_transcription.srt", "").replace(".srt", "")
                c_segments = parse_srt(c_file)
                
                start, end = find_segment_range(main_segments, c_segments)
                if start and end:
                    results.append(f"{start} - {end} : {name}")
                    print(f" [+] Trouvé : {name} ({os.path.basename(root)})")
                else:
                    not_found.append(name)
                    print(f" [-] Non trouvé : {name}")

            if results or not_found:
                # Nom de fichier de sortie basé sur le chemin (ex: 2.rtl-matin_06-04.txt)
                folder_id = "_".join(root.split(os.sep)[-2:]).replace(":", "-")
                with open(os.path.join(output_dir, f"{folder_id}.txt"), 'w', encoding='utf-8') as out:
                    if results:
                        out.write("\n".join(results) + "\n")
                    if not_found:
                        out.write("\n\nNON TROUVÉES :\n")
                        out.write("\n".join(not_found) + "\n")

if __name__ == "__main__":
    main()
