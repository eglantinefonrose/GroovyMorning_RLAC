import os
import re
import sys
import argparse
from pathlib import Path
from pydub import AudioSegment

# Seuil de 2 minutes en millisecondes
GAP_THRESHOLD_MS = 2 * 60 * 1000

def parse_timecode(tc_str):
    """Convertit [HH:MM:SS:mmm] ou [HH:MM:SS.mmm] en millisecondes."""
    tc_str = tc_str.strip("[] ")
    match = re.match(r'(\d+):(\d+):(\d+)[:.](\d+)', tc_str)
    if match:
        h, m, s, ms = map(int, match.groups())
        return ((h * 3600 + m * 60 + s) * 1000) + ms
    
    match = re.match(r'(\d+):(\d+):(\d+)', tc_str)
    if match:
        h, m, s = map(int, match.groups())
        return (h * 3600 + m * 60 + s) * 1000
        
    raise ValueError(f"Format de timecode inconnu : {tc_str}")

def format_timecode(total_ms):
    """Convertit les millisecondes en [HH:MM:SS:mmm]."""
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"[{h:02d}:{m:02d}:{s:02d}:{ms:03d}]"

def find_audio_file(dossier_path):
    """Trouve le premier fichier .mp3 ou .m4a dans dossier_path, en ignorant les dossiers 'chroniques'."""
    for root, dirs, files in os.walk(dossier_path):
        if 'chroniques' in Path(root).parts:
            continue
        for file in files:
            if file.lower().endswith(('.mp3', '.m4a')) and not file.endswith('_trimmed' + Path(file).suffix):
                return Path(root) / file
    return None

def process_single_audio(audio_file, timecode_file, radio_dir):
    """Applique la logique de trimming pour un couple audio/timecode."""
    print(f"\nTraitement de : {audio_file.name}")
    print(f"Timecode : {timecode_file}")

    try:
        audio = AudioSegment.from_file(str(audio_file))
    except Exception as e:
        print(f"  Erreur chargement audio : {e}")
        return False

    segments = []
    try:
        with open(timecode_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'(\[.*?\])\s*-\s*(\[.*?\])(.*)', line)
                if match:
                    try:
                        start = parse_timecode(match.group(1))
                        end = parse_timecode(match.group(2))
                        name = match.group(3).strip()
                        segments.append((start, end, name))
                    except ValueError:
                        continue
    except Exception as e:
        print(f"  Erreur lecture timecode : {e}")
        return False

    if not segments:
        print("  Aucun segment trouvé.")
        return False

    segments.sort()
    final_audio = AudioSegment.empty()
    new_segments_tc = []
    current_out_ms = 0
    
    for i in range(len(segments)):
        start, end, name = segments[i]
        if i > 0:
            prev_end = segments[i-1][1]
            gap_ms = start - prev_end
            if gap_ms <= GAP_THRESHOLD_MS and gap_ms > 0:
                gap_audio = audio[prev_end:start]
                final_audio += gap_audio
                current_out_ms += len(gap_audio)
        
        seg_audio = audio[start:end]
        new_start = current_out_ms
        final_audio += seg_audio
        current_out_ms += len(seg_audio)
        new_segments_tc.append((new_start, current_out_ms, name))

    output_audio_path = audio_file.parent / f"{audio_file.stem}_trimmed{audio_file.suffix}"
    try:
        fmt = audio_file.suffix.lower().strip('.')
        final_audio.export(str(output_audio_path), format=fmt if fmt != 'm4a' else 'mp4')
        print(f"  Audio exporté : {output_audio_path.name}")
    except Exception as e:
        print(f"  Erreur export audio : {e}")
        return False

    news_dir = radio_dir / "news"
    news_dir.mkdir(exist_ok=True)
    output_tc_path = news_dir / f"{audio_file.stem}_new_from_audio.txt"
    try:
        with open(output_tc_path, 'w', encoding='utf-8') as f:
            for ns, ne, name in new_segments_tc:
                suffix = f" {name}" if name else ""
                f.write(f"{format_timecode(ns)} - {format_timecode(ne)}{suffix}\n")
        print(f"  Timecodes exportés : {output_tc_path.name}")
    except Exception as e:
        print(f"  Erreur export timecodes : {e}")
        return False

    return True

def main():
    current_dir = Path.cwd().absolute()
    assets_root = None
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "@assets").exists():
            assets_root = parent / "@assets"
            break
    
    if not assets_root:
        assets_root = (current_dir / "../../../@assets").resolve()

    media_root = assets_root / "0.media"
    timecode_base_root = assets_root / "2.humanOutputs" / "1.timecode-segments" / "2.audio-analyse" / "timecode_chroniques"

    if not timecode_base_root.exists():
        print(f"Erreur : Dossier timecode introuvable à {timecode_base_root}")
        sys.exit(1)

    print(f"Scan des timecodes dans : {timecode_base_root}")
    
    # On cherche tous les fichiers timecode_chroniques_*.txt
    timecode_files = list(timecode_base_root.rglob("timecode_chroniques_*.txt"))
    
    if not timecode_files:
        print("Aucun fichier de timecode trouvé.")
        return

    processed_count = 0
    for tc_file in timecode_files:
        # On ignore les fichiers déjà dans un dossier 'news' s'il y en a
        if 'news' in tc_file.parts:
            continue
            
        # Extraction du nom du dossier depuis le nom du fichier
        # Pattern: timecode_chroniques_{nom_dossier}.txt
        match = re.search(r'timecode_chroniques_(.*)\.txt$', tc_file.name)
        if not match:
            continue
            
        nom_dossier = match.group(1)
        
        # Le nom de la radio est souvent le parent ou grand-parent
        # Dans la structure : .../timecode_chroniques/<radio>/<date>/file.txt
        # Ou .../timecode_chroniques/1.rtl-matin/<radio>/...
        radio_dir = None
        # On remonte pour trouver le dossier qui est directement sous timecode_chroniques ou 1.rtl-matin
        for p in tc_file.parents:
            if p.parent == timecode_base_root or (p.parent.name == "1.rtl-matin" and p.parent.parent == timecode_base_root):
                radio_dir = p
                break
        
        if not radio_dir:
            radio_dir = tc_file.parent

        nom_radio = radio_dir.name
        
        # Recherche de l'audio dans 0.media
        target_media_dir = None
        for p in media_root.rglob(nom_dossier):
            if p.is_dir() and nom_radio.lower() in str(p).lower():
                target_media_dir = p
                break
        
        if target_media_dir:
            audio_file = find_audio_file(target_media_dir)
            if audio_file:
                if process_single_audio(audio_file, tc_file, radio_dir):
                    processed_count += 1
            else:
                print(f"Audio non trouvé pour {nom_dossier} dans {target_media_dir}")
        else:
            print(f"Dossier media non trouvé pour {nom_dossier} ({nom_radio})")

    print(f"\nTerminé. {processed_count} fichiers traités.")

if __name__ == "__main__":
    main()
