import sys
import os
import numpy as np
import librosa
from scipy import signal
import datetime
import re

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
    Utilise la corrélation croisée via FFT pour l'alignement global,
    puis affine les bornes en vérifiant la similarité locale.
    """
    # Normalisation du needle
    y_needle_norm = (y_needle - np.mean(y_needle)) / (np.std(y_needle) + 1e-9)

    # 1. Alignement global via corrélation FFT
    correlation = signal.fftconvolve(y_haystack_norm, y_needle_norm[::-1], mode='full')
    peak_index = np.argmax(correlation)

    # Offset : index dans le haystack où le début du needle est aligné
    offset = peak_index - len(y_needle_norm) + 1

    # 2. Affinement des bornes (recherche de la portion réellement présente)
    # On découpe le needle en blocs pour vérifier la corrélation locale
    win_size = int(sr * 0.2)  # Fenêtres de 200ms
    if win_size == 0: win_size = 1

    num_wins = len(y_needle) // win_size
    similarities = []

    for i in range(num_wins):
        start_n = i * win_size
        end_n = start_n + win_size

        start_h = offset + start_n
        end_h = start_h + win_size

        # Si le bloc est hors des limites du haystack, similarity = 0
        if start_h < 0 or end_h > len(y_haystack_norm):
            similarities.append(0)
            continue

        # Calcul de la corrélation locale sur ce bloc
        chunk_n = y_needle_norm[start_n:end_n]
        chunk_h = y_haystack_norm[start_h:end_h]

        # Corrélation de Pearson simplifiée (les chunks sont déjà +/- centrés)
        corr = np.sum(chunk_n * chunk_h) / (np.sqrt(np.sum(chunk_n ** 2) * np.sum(chunk_h ** 2)) + 1e-9)
        similarities.append(corr)

    similarities = np.array(similarities)

    # Seuil de corrélation locale (0.25 est assez bas mais robuste aux bruits/différences mineures)
    threshold = 0.25
    matches = similarities > threshold

    if not np.any(matches):
        return offset / sr, (offset + len(y_needle)) / sr

    first_match_idx = np.where(matches)[0][0]
    last_match_idx = np.where(matches)[0][-1]

    # Calcul des nouveaux timecodes
    start_time = (offset + first_match_idx * win_size) / sr
    end_time = (offset + (last_match_idx + 1) * win_size) / sr

    return start_time, end_time

def process_single_date(radio_name, date_str, chroniques_dir, haystack_path, output_radio_dir):
    """Exécute l'analyse pour une date donnée."""
    output_filename = f"timecode_chroniques_{date_str}.txt"
    output_path = os.path.join(output_radio_dir, output_filename)

    # Vérification si le fichier existe déjà
    if os.path.exists(output_path):
        print(f"[!] Saut de {date_str} : le fichier existe déjà ({output_filename})")
        return

    print(f"\n[*] --- Traitement de {date_str} ---")
    
    sr = 16000
    print(f"[*] Chargement du fichier complet : {os.path.basename(haystack_path)}")
    try:
        y_haystack, _ = librosa.load(haystack_path, sr=sr, mono=True)
    except Exception as e:
        print(f"    [!] Erreur chargement haystack: {e}")
        return

    print("[*] Normalisation...")
    y_haystack_norm = (y_haystack - np.mean(y_haystack)) / (np.std(y_haystack) + 1e-9)
    haystack_duration = len(y_haystack) / sr

    results = []
    audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.ogg')
    files_to_process = sorted([f for f in os.listdir(chroniques_dir) if f.lower().endswith(audio_extensions)])

    if not files_to_process:
        print(f"    [!] Aucun fichier audio dans {chroniques_dir}")
        return

    for filename in files_to_process:
        needle_path = os.path.join(chroniques_dir, filename)
        try:
            y_needle, _ = librosa.load(needle_path, sr=sr, mono=True)
            start, end = find_audio_match(y_needle, y_haystack_norm, sr)
            actual_start = max(0, start)
            actual_end = min(haystack_duration, end)
            results.append({'start': actual_start, 'end': actual_end, 'name': filename})
            print(f"      - {filename} -> {format_time(actual_start)} - {format_time(actual_end)}")
        except Exception as e:
            print(f"      [!] Erreur sur {filename} : {e}")

    if not results:
        return

    results.sort(key=lambda x: x['start'])

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for res in results:
                line = f"[{format_time(res['start'])}] - [{format_time(res['end'])}] {res['name']}"
                f.write(line + "\n")
        print(f"[*] Succès : {output_path}")
    except Exception as e:
        print(f"    [!] Erreur écriture: {e}")

def main():
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python find_all_chroniques_in_directories.py <dossier_racine>")
        print("\nExemple:")
        print("  python find_all_chroniques_in_directories.py ../../../0.media/audio/")
        sys.exit(1)

    root_dir = sys.argv[1]
    if not os.path.isdir(root_dir):
        print(f"Erreur : '{root_dir}' n'est pas un dossier.")
        sys.exit(1)

    # Regex pour détecter les dossiers de date (ex: 13-04-2026)
    date_pattern = re.compile(r'^\d{2}-\d{2}-\d{4}$')

    processed_count = 0
    skipped_count = 0
    
    # Parcours récursif de toute l'arborescence
    for current_root, dirs, files in os.walk(root_dir):
        for d in dirs:
            if date_pattern.match(d):
                date_dir = os.path.join(current_root, d)
                chroniques_dir = os.path.join(date_dir, "chroniques")
                
                # Recherche du fichier haystack (.mp3 ou .m4a)
                haystack_path = None
                for ext in [".mp3", ".m4a"]:
                    test_path = os.path.join(date_dir, f"{d}{ext}")
                    if os.path.exists(test_path):
                        haystack_path = test_path
                        break

                # On vérifie si les éléments nécessaires sont là
                if os.path.isdir(chroniques_dir) and haystack_path:
                    # Calcul explicite du nom de la radio : 2 niveaux au-dessus du fichier audio
                    # Audio -> Dossier Date (1) -> Dossier Radio (2)
                    path_level_1 = os.path.dirname(haystack_path)
                    path_level_2 = os.path.dirname(path_level_1)
                    radio_name = os.path.basename(path_level_2)
                    
                    # Dossier de sortie : timecode_chroniques/{radio_name}/
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    output_radio_dir = os.path.join(script_dir, "timecode_chroniques", radio_name)
                    
                    output_filename = f"timecode_chroniques_{d}.txt"
                    output_path = os.path.join(output_radio_dir, output_filename)

                    # Vérification de l'existence (dans le dossier radio ou à la racine pour compatibilité)
                    output_path_root = os.path.join(script_dir, "timecode_chroniques", output_filename)

                    if os.path.exists(output_path) or os.path.exists(output_path_root):
                        print(f"[#] Saut de {d} ({radio_name}) : fichier txt déjà présent.")
                        skipped_count += 1
                        continue

                    os.makedirs(output_radio_dir, exist_ok=True)
                    process_single_date(radio_name, d, chroniques_dir, haystack_path, output_radio_dir)
                    processed_count += 1

    if processed_count == 0 and skipped_count == 0:
        print(f"Aucun dossier de date valide trouvé dans '{root_dir}'.")
    else:
        print(f"\n[*] Synthèse : {processed_count} analysés, {skipped_count} sautés (déjà existants).")

if __name__ == "__main__":
    main()
