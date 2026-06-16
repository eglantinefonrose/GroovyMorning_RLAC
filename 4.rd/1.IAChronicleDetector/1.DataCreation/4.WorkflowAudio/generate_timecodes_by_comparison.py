import os
import re
import sys
import argparse
import numpy as np
import librosa
from scipy import signal
from pathlib import Path
import datetime

# --- LOGIQUE ISSUE DE audio-analyse/find_all_chroniques.py ---

def format_time(seconds):
    """Convertit des secondes en format HH:MM:SS.mmm"""
    td = datetime.timedelta(seconds=seconds)
    total_seconds = td.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def find_audio_match(y_needle, y_haystack_norm, sr):
    """
    Trouve la meilleure correspondance de y_needle dans y_haystack_norm.
    Utilise la corrélation croisée via FFT pour l'alignement global.
    """
    # Normalisation du needle
    y_needle_norm = (y_needle - np.mean(y_needle)) / (np.std(y_needle) + 1e-9)

    # 1. Alignement global via corrélation FFT
    correlation = signal.fftconvolve(y_haystack_norm, y_needle_norm[::-1], mode='full')
    peak_index = np.argmax(correlation)

    # Offset : index dans le haystack où le début du needle est aligné
    offset = peak_index - len(y_needle_norm) + 1

    # 2. Affinement des bornes (recherche de la portion réellement présente)
    win_size = int(sr * 0.2)  # Fenêtres de 200ms
    if win_size == 0: win_size = 1

    num_wins = len(y_needle) // win_size
    similarities = []

    for i in range(num_wins):
        start_n = i * win_size
        end_n = start_n + win_size
        start_h = offset + start_n
        end_h = start_h + win_size

        if start_h < 0 or end_h > len(y_haystack_norm):
            similarities.append(0)
            continue

        chunk_n = y_needle_norm[start_n:end_n]
        chunk_h = y_haystack_norm[start_h:end_h]
        corr = np.sum(chunk_n * chunk_h) / (np.sqrt(np.sum(chunk_n ** 2) * np.sum(chunk_h ** 2)) + 1e-9)
        similarities.append(corr)

    similarities = np.array(similarities)
    threshold = 0.25
    matches = similarities > threshold

    if not np.any(matches):
        return offset / sr, (offset + len(y_needle)) / sr

    first_match_idx = np.where(matches)[0][0]
    last_match_idx = np.where(matches)[0][-1]

    start_time = (offset + first_match_idx * win_size) / sr
    end_time = (offset + (last_match_idx + 1) * win_size) / sr

    return start_time, end_time

# --- LOGIQUE DE DÉCOUVERTE ET SORTIE ---

def main():
    parser = argparse.ArgumentParser(description="Génère un fichier de timecodes par corrélation audio (Méthode audio-analyse).")
    parser.add_argument("--radio", help="Nom de la radio (ex: rtl, france-inter)")
    parser.add_argument("--date", help="Date (YYYY-MM-DD)")
    parser.add_argument("--haystack", help="Chemin direct vers le fichier audio complet (meule de foin)")
    parser.add_argument("--chroniques-dir", help="Chemin direct vers le dossier contenant les extraits (aiguilles)")
    parser.add_argument("--output", help="Chemin direct pour le fichier de sortie .txt")
    args = parser.parse_args()

    # Vérification des arguments minimaux
    if not ((args.radio and args.date) or (args.haystack and args.chroniques_dir)):
        parser.error("Vous devez fournir soit (--radio ET --date) pour la découverte automatique, "
                     "soit (--haystack ET --chroniques-dir) pour un usage manuel.")

    # 1. Préparation des variables de base
    radio_filter = args.radio.lower().replace("-", "").replace(" ", "") if args.radio else "manual"
    date_iso = args.date if args.date else datetime.datetime.now().strftime('%Y-%m-%d')
    
    try:
        dt = datetime.datetime.strptime(date_iso, '%Y-%m-%d')
        date_dmy = dt.strftime('%d-%m-%Y')
    except ValueError:
        print(f"❌ Format de date invalide : {date_iso}. Utilisez YYYY-MM-DD.")
        sys.exit(1)

    current_dir = Path.cwd().absolute()
    assets_root = None
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "@assets").exists():
            assets_root = parent / "@assets"
            break
    
    # 2. Localisation du haystack (audio principal) et des chroniques
    haystack_path = None
    chron_files = []

    if args.haystack and args.chroniques_dir:
        # Mode Manuel
        haystack_path = Path(args.haystack)
        chron_dir = Path(args.chroniques_dir)
        
        if not haystack_path.exists():
            print(f"❌ Fichier haystack introuvable : {haystack_path}")
            sys.exit(1)
        if not chron_dir.is_dir():
            print(f"❌ Dossier des chroniques introuvable : {chron_dir}")
            sys.exit(1)
            
        audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.ogg')
        chron_files = sorted([f for f in chron_dir.glob("*") if f.suffix.lower() in audio_extensions])
    else:
        # Mode Automatique (découverte via @assets)
        if not assets_root:
            print("❌ Erreur : Impossible de trouver le dossier @assets pour la découverte automatique.")
            sys.exit(1)

        media_root = assets_root / "0.media" / "audio"
        best_date_dir = None
        date_formats = [dt.strftime('%d-%m-%Y'), dt.strftime('%Y-%m-%d'), dt.strftime('%d-%m-%y')]

        for radio_dir in media_root.iterdir():
            if not radio_dir.is_dir(): continue
            radio_clean = radio_dir.name.lower().replace("-", "").replace(" ", "")
            if radio_filter in radio_clean:
                for fmt in date_formats:
                    test_dir = radio_dir / fmt
                    if test_dir.exists():
                        best_date_dir = test_dir
                        break
            if best_date_dir: break
        
        if not best_date_dir:
            print(f"❌ Dossier média introuvable pour {args.radio} le {date_dmy}")
            sys.exit(1)

        print(f"🔍 Utilisation du dossier média : {best_date_dir.relative_to(assets_root)}")
        
        audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.ogg')
        max_size = -1
        for f in best_date_dir.glob("*"):
            if f.suffix.lower() in audio_extensions:
                if f.stat().st_size > max_size:
                    max_size = f.stat().st_size
                    haystack_path = f

        chron_dir = best_date_dir / "chroniques"
        if chron_dir.exists():
            chron_files = sorted([f for f in chron_dir.glob("*") if f.suffix.lower() in audio_extensions])

    # 3. Validations finales avant analyse
    if not haystack_path or not haystack_path.exists():
        print("❌ Fichier audio principal introuvable.")
        sys.exit(1)

    if not chron_files:
        print(f"⚠️ Aucun fichier audio trouvé dans le dossier des chroniques.")
        sys.exit(0)

    # 4. Chargement et analyse
    sr = 16000
    print(f"[*] Chargement de l'audio complet : {haystack_path.name}")
    try:
        y_haystack, _ = librosa.load(str(haystack_path), sr=sr, mono=True)
        y_haystack_norm = (y_haystack - np.mean(y_haystack)) / (np.std(y_haystack) + 1e-9)
        haystack_duration = len(y_haystack) / sr
    except Exception as e:
        print(f"❌ Erreur lors du chargement de l'audio principal : {e}")
        sys.exit(1)

    results = []
    print(f"[*] Analyse de {len(chron_files)} chroniques...")
    for c_file in chron_files:
        print(f"    - {c_file.name}")
        try:
            y_needle, _ = librosa.load(str(c_file), sr=sr, mono=True)
            start, end = find_audio_match(y_needle, y_haystack_norm, sr)
            
            actual_start = max(0, start)
            actual_end = min(haystack_duration, end)
            
            results.append(f"[{format_time(actual_start)}] - [{format_time(actual_end)}] {c_file.name}")
            print(f"      ✅ Trouvé : {format_time(actual_start)} - {format_time(actual_end)}")
        except Exception as e:
            print(f"      ❌ Erreur : {e}")

    if not results:
        print("ℹ️ Aucune chronique localisée.")
        sys.exit(0)

    # 5. Sortie des résultats
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
    elif assets_root:
        output_base = assets_root / "2.humanOutputs" / "1.timecode-segments" / "2.audio-analyse" / "timecode_chroniques"
        radio_out_dir = None
        for d in output_base.iterdir():
            if d.is_dir() and radio_filter in d.name.lower().replace("-", "").replace(" ", ""):
                radio_out_dir = d
                break
        
        if not radio_out_dir:
            radio_out_dir = output_base / (args.radio if args.radio else "manual_uploads")
            radio_out_dir.mkdir(parents=True, exist_ok=True)

        output_file = radio_out_dir / f"timecode_chroniques_{date_dmy}.txt"
    else:
        output_file = Path.cwd() / f"timecode_chroniques_{date_dmy}.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(results) + "\n")
    
    print(f"\n✨ Timecodes générés : {output_file}")

if __name__ == "__main__":
    main()
