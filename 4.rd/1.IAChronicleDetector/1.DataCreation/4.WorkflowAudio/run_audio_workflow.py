import os
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime
from pydub import AudioSegment

# Seuil de 2 minutes en millisecondes (pour le trimming)
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

def find_audio_file(dossier_path, skip_trimmed=True):
    """Trouve le premier fichier .mp3 ou .m4a dans dossier_path."""
    for root, dirs, files in os.walk(dossier_path):
        if 'chroniques' in Path(root).parts:
            continue
        for file in files:
            if file.lower().endswith(('.mp3', '.m4a')):
                is_trimmed = file.endswith('_trimmed' + Path(file).suffix)
                if skip_trimmed and is_trimmed:
                    continue
                if not is_trimmed:
                    return Path(root) / file
    return None

def check_if_already_trimmed(audio_file):
    """Vérifie si un fichier _trimmed existe déjà pour cet audio."""
    trimmed_path = audio_file.parent / f"{audio_file.stem}_trimmed{audio_file.suffix}"
    return trimmed_path.exists()

def extract_date_from_string(s):
    """Tente d'extraire une date au format YYYY-MM-DD ou DD-MM-YYYY."""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    
    match = re.search(r'(\d{2}-\d{2}-\d{4})', s)
    if match:
        try:
            return datetime.strptime(match.group(1), '%d-%m-%Y')
        except ValueError:
            pass
            
    return None

def process_trimming(audio_file, timecode_file, radio_dir, output_name_prefix=None):
    """Logique de trimming (reprise de 3.AudioMediaTrimming)."""
    print(f"  Traitement de : {audio_file.name}")
    
    try:
        audio = AudioSegment.from_file(str(audio_file))
    except Exception as e:
        print(f"    ❌ Erreur chargement audio : {e}")
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
        print(f"    ❌ Erreur lecture timecode : {e}")
        return False

    if not segments:
        print("    ⚠️ Aucun segment trouvé dans le fichier de timecode.")
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
        print(f"    ✅ Audio exporté : {output_audio_path.name}")
    except Exception as e:
        print(f"    ❌ Erreur export audio : {e}")
        return False

    news_dir = radio_dir / "news"
    news_dir.mkdir(exist_ok=True)
    
    # Utilisation du préfixe s'il est fourni (ex: la date), sinon le nom du fichier audio
    output_prefix = output_name_prefix if output_name_prefix else audio_file.stem
    output_tc_path = news_dir / f"{output_prefix}_new_from_audio.txt"
    
    try:
        with open(output_tc_path, 'w', encoding='utf-8') as f:
            for ns, ne, name in new_segments_tc:
                suffix = f" {name}" if name else ""
                f.write(f"{format_timecode(ns)} - {format_timecode(ne)}{suffix}\n")
        print(f"    ✅ Timecodes exportés : {output_tc_path.name}")
    except Exception as e:
        print(f"    ❌ Erreur export timecodes : {e}")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description="Workflow Audio Automatique avec filtrage par date et détection de doublons.")
    parser.add_argument("--date", help="Date spécifique (YYYY-MM-DD)", type=str)
    parser.add_argument("--start", help="Date de début (YYYY-MM-DD)", type=str)
    parser.add_argument("--end", help="Date de fin (YYYY-MM-DD)", type=str)
    parser.add_argument("--radio", help="Limiter à une radio spécifique (ex: rtl, france-inter)", type=str)
    parser.add_argument("--force", help="Forcer le re-traitement même si le fichier _trimmed existe", action="store_true")
    parser.add_argument("--dry-run", help="Afficher ce qui serait fait sans exécuter", action="store_true")
    
    args = parser.parse_args()

    if args.date:
        start_date = datetime.strptime(args.date, '%Y-%m-%d')
        end_date = start_date
    else:
        start_date = datetime.strptime(args.start, '%Y-%m-%d') if args.start else None
        end_date = datetime.strptime(args.end, '%Y-%m-%d') if args.end else None
    
    # Nettoyage du filtre radio pour plus de souplesse (ex: france-inter -> franceinter)
    radio_filter = args.radio.lower().replace("-", "").replace(" ", "") if args.radio else None

    # Recherche de @assets
    current_dir = Path.cwd().absolute()
    assets_root = None
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "@assets").exists():
            assets_root = parent / "@assets"
            break
    
    if not assets_root:
        # Fallback si non trouvé par remontée
        assets_root = (current_dir / "../@assets").resolve()
        if not assets_root.exists():
            print("Erreur : Impossible de trouver le dossier @assets")
            sys.exit(1)

    media_root = assets_root / "0.media"
    timecode_base_root = assets_root / "2.humanOutputs" / "1.timecode-segments" / "2.audio-analyse" / "timecode_chroniques"

    if not timecode_base_root.exists():
        print(f"Erreur : Dossier timecode introuvable à {timecode_base_root}")
        sys.exit(1)

    print(f"--- WORKFLOW AUDIO ---")
    print(f"Assets : {assets_root}")
    if start_date: print(f"Début  : {start_date.date()}")
    if end_date:   print(f"Fin    : {end_date.date()}")
    if radio_filter: print(f"Radio  : {radio_filter}")
    if args.force: print("Mode   : FORCE (écrase les fichiers existants)")
    if args.dry_run: print("Mode   : DRY-RUN (aucune modification)")
    print("-" * 20)

    timecode_files = list(timecode_base_root.rglob("timecode_chroniques_*.txt"))
    
    processed_count = 0
    skipped_count = 0
    date_filtered_count = 0
    radio_filtered_count = 0

    for tc_file in timecode_files:
        if 'news' in tc_file.parts:
            continue
            
        match = re.search(r'timecode_chroniques_(.*)\.txt$', tc_file.name)
        if not match:
            continue
            
        nom_dossier = match.group(1)
        file_date = extract_date_from_string(nom_dossier)
        
        # Liste des formats possibles pour le nom du dossier média
        possibilites_nom = [nom_dossier]
        if file_date:
            possibilites_nom.append(file_date.strftime("%Y-%m-%d"))
            possibilites_nom.append(file_date.strftime("%d-%m-%Y"))
            possibilites_nom.append(file_date.strftime("%d-%m-%y"))

        # Filtrage par date
        if file_date:
            if start_date and file_date < start_date:
                date_filtered_count += 1
                continue
            if end_date and file_date > end_date:
                date_filtered_count += 1
                continue
        
        # Détermination de la radio
        radio_dir = None
        for p in tc_file.parents:
            if p.parent == timecode_base_root or (p.parent.name == "1.rtl-matin" and p.parent.parent == timecode_base_root):
                radio_dir = p
                break
        if not radio_dir:
            radio_dir = tc_file.parent

        nom_radio = radio_dir.name

        # Filtrage par radio
        if radio_filter:
            clean_radio_name = nom_radio.lower().replace("-", "").replace(" ", "")
            if radio_filter not in clean_radio_name:
                radio_filtered_count += 1
                continue
        
        # Recherche media
        target_media_dir = None
        # On scanne TOUT media_root pour trouver un dossier qui contient la date ET la radio
        for root, dirs, files in os.walk(media_root):
            for d in dirs:
                # Si le nom du dossier est une de nos dates cibles
                if d in possibilites_nom:
                    full_path = Path(root) / d
                    path_str = full_path.as_posix().lower().replace("-", "").replace(" ", "")
                    radio_clean = nom_radio.lower().replace("-", "").replace(" ", "")
                    
                    # On vérifie si la radio est mentionnée dans le chemin (ex: franceinter)
                    if radio_clean in path_str or radio_filter in path_str:
                        target_media_dir = full_path
                        break
            if target_media_dir:
                break
        
        if target_media_dir:
            print(f"    🔍 Dossier media trouvé : {target_media_dir}")
            audio_file = find_audio_file(target_media_dir)
            if audio_file:
                already_done = check_if_already_trimmed(audio_file)
                
                if already_done and not args.force:
                    print(f"⏭️  Déjà traité : {nom_dossier} ({nom_radio})")
                    skipped_count += 1
                    continue
                
                print(f"🎬 Traitement : {nom_dossier} ({nom_radio})")
                if not args.dry_run:
                    if process_trimming(audio_file, tc_file, radio_dir, output_name_prefix=nom_dossier):
                        processed_count += 1
                else:
                    processed_count += 1
            else:
                print(f"    ❓ Audio non trouvé dans : {target_media_dir}")
        else:
            # print(f"❓ Dossier media non trouvé pour {nom_dossier}")
            pass

    print(f"\n--- BILAN ---")
    print(f"Total fichiers trouvés : {len(timecode_files)}")
    print(f"Filtre date (exclus)   : {date_filtered_count}")
    print(f"Filtre radio (exclus)  : {radio_filtered_count}")
    print(f"Déjà traités (sautés)  : {skipped_count}")
    print(f"Traités avec succès    : {processed_count}")
    print("Terminé.")

if __name__ == "__main__":
    main()
