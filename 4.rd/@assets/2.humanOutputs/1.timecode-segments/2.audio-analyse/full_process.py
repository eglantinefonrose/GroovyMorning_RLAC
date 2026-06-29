#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import re
import unicodedata
from datetime import datetime
from pathlib import Path

# ==============================================================================
# CONFIGURATION ET CHEMINS
# ==============================================================================

# Structure : [PROJECT_ROOT]/@assets/2.humanOutputs/1.timecode-segments/2.audio-analyse/full_process.py
SCRIPT_PATH = Path(__file__).resolve()
ASSETS_DIR = SCRIPT_PATH.parents[3]
PROJECT_ROOT = SCRIPT_PATH.parents[4]

# Paramètres Kyutai
KYUTAI_SCRIPT = PROJECT_ROOT / "1.IAChronicleDetector/1.DataCreation/2.TranscriptionGeneration/prt-generate-transcripts-with-kyutai_stt_2.6b_fr.py"
TRANSCRIPTION_DIR = ASSETS_DIR / "1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
OUTPUT_TIMECODE_DIR = ASSETS_DIR / "2.humanOutputs/1.timecode-segments/1.automatic-from-chronique-transcription"

RADIO_MAPPING = {
    "inter": {
        "script": "1.IAChronicleDetector/1.DataCreation/0.DownloadChroniquesAndFullRadioProgramAutomaticly/france-inter/download_franceinter_range.py",
        "audio_dir": "4.franceinter-matin"
    },
    "info": {
        "script": "1.IAChronicleDetector/1.DataCreation/0.DownloadChroniquesAndFullRadioProgramAutomaticly/france-info/download_franceinfo_range.py",
        "audio_dir": "2.franceinfo-matin"
    },
    "culture": {
        "script": "1.IAChronicleDetector/1.DataCreation/0.DownloadChroniquesAndFullRadioProgramAutomaticly/france-culture/download_franceculture_range.py",
        "audio_dir": "3.franceculture-matin"
    },
    "rtl": {
        "script": "1.IAChronicleDetector/1.DataCreation/0.DownloadChroniquesAndFullRadioProgramAutomaticly/rtl/download_rtl_range.py",
        "audio_dir": "5.rtl-matin"
    }
}

# ==============================================================================
# LOGIQUE D'ALIGNEMENT (Basée sur le TEXTE)
# ==============================================================================

def format_timecode(seconds):
    """Convertit des secondes en [HH:MM:SS:mmm]."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds * 1000) % 1000)
    return f"[{h:02d}:{m:02d}:{s:02d}:{ms:03d}]"

def normalize(text):
    if not text: return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn']).lower()
    return re.sub(r'[^a-z0-9]', '', text)

def find_segment_range_text(main_text, chron_text, main_duration):
    """
    Cherche la chronique dans l'intégrale en utilisant uniquement le texte.
    Estime les timecodes au prorata de la position des caractères.
    """
    norm_main = normalize(main_text)
    norm_chron = normalize(chron_text)
    
    if not norm_chron or not norm_main: return None, None
    
    # On cherche des chunks significatifs de la chronique
    # On prend les 100 premiers caractères normalisés (ou moins si texte court)
    chunk_size = min(100, len(norm_chron))
    start_chunk = norm_chron[:chunk_size]
    end_chunk = norm_chron[-chunk_size:]
    
    match_start = norm_main.find(start_chunk)
    if match_start == -1:
        # Tentative avec un chunk plus court si pas trouvé
        chunk_size = min(50, len(norm_chron))
        start_chunk = norm_chron[:chunk_size]
        match_start = norm_main.find(start_chunk)
        
    if match_start != -1:
        match_end = norm_main.find(end_chunk, match_start)
        if match_end == -1:
            # Estimation de la fin basée sur la longueur de la chronique
            match_end = match_start + len(norm_chron)
        else:
            match_end += len(end_chunk)
            
        # Conversion position -> secondes (estimation linéaire par rapport au nombre de caractères)
        total_chars = len(norm_main)
        start_sec = (match_start / total_chars) * main_duration
        end_sec = (match_end / total_chars) * main_duration
        
        return format_timecode(start_sec), format_timecode(end_sec)
    
    return None, None

def get_audio_duration(file_path):
    """Récupère la durée de l'audio via ffprobe."""
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return 0

# ==============================================================================
# WORKFLOW PRINCIPAL
# ==============================================================================

def run_step(name, cmd, cwd=None):
    print(f"\n--- [ÉTAPE] {name} ---")
    print(f"Commande : {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'étape {name}")
        return False

def transcribe_kyutai(audio_file, txt_file):
    if txt_file.exists():
        print(f"   ✅ Déjà transcrit : {txt_file.name}")
        return True
    
    print(f"   🔄 Transcription Kyutai de : {audio_file.name}")
    txt_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Utilisation du python du venv si disponible, sinon sys.executable
    python_exe = KYUTAI_PYTHON if KYUTAI_PYTHON.exists() else sys.executable
    
    # Appel du script Kyutai avec --no-srt et --stdout
    cmd = [str(python_exe), str(KYUTAI_SCRIPT), "-i", str(audio_file.absolute()), "--no-srt", "--stdout"]
    try:
        # On capture la sortie standard qui contient la transcription
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        return True
    except Exception as e:
        print(f"   ❌ Erreur transcription : {e}")
        if hasattr(e, 'stderr') and e.stderr: 
            print(f"      Détail erreur :\n{e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Workflow complet : Téléchargement + Transcription Kyutai (Texte) + Timecodes")
    parser.add_argument("radio", choices=["inter", "info", "culture", "rtl"], help="Nom de la radio")
    parser.add_argument("date", help="Date au format DD-MM-YYYY (ex: 20-05-2026)")
    parser.add_argument("--skip-download", action="store_true", help="Sauter l'étape de téléchargement")
    
    args = parser.parse_args()
    
    radio_info = RADIO_MAPPING[args.radio]
    audio_dir_name = radio_info["audio_dir"]
    date_str = args.date
    
    # 1. TÉLÉCHARGEMENT
    if not args.skip_download:
        script_path = PROJECT_ROOT / radio_info["script"]
        run_step("Téléchargement", [sys.executable, str(script_path), date_str, date_str], cwd=script_path.parent)

    # Chemins des médias
    media_date_dir = ASSETS_DIR / "0.media/audio" / audio_dir_name / date_str
    if not media_date_dir.exists():
        # Tentative si le dossier a un nom légèrement différent
        alt_dirs = list((ASSETS_DIR / "0.media/audio").glob(f"*{args.radio}*"))
        found = False
        for ad in alt_dirs:
            if (ad / date_str).exists():
                media_date_dir = ad / date_str
                audio_dir_name = ad.name
                found = True
                break
        if not found:
            print(f"❌ Dossier média introuvable pour la date {date_str} dans {ASSETS_DIR / '0.media/audio'}")
            sys.exit(1)

    # 2. TRANSCRIPTION
    print(f"\n--- [ÉTAPE] Transcription (Kyutai) ---")
    
    # Trouver l'intégrale (le plus gros fichier à la racine du dossier date)
    audio_files = list(media_date_dir.glob("*.mp3")) + list(media_date_dir.glob("*.m4a"))
    if not audio_files:
        print(f"❌ Aucun fichier audio trouvé dans {media_date_dir}")
        sys.exit(1)
        
    integrale_file = sorted(audio_files, key=lambda x: x.stat().st_size, reverse=True)[0]
    integrale_txt = TRANSCRIPTION_DIR / audio_dir_name / date_str / f"{integrale_file.stem}_transcription.txt"
    
    transcribe_kyutai(integrale_file, integrale_txt)
    
    # Chroniques
    chroniques_dir = media_date_dir / "chroniques"
    if chroniques_dir.exists():
        chron_files = list(chroniques_dir.glob("*.mp3")) + list(chroniques_dir.glob("*.m4a"))
        for cf in chron_files:
            ctxt = TRANSCRIPTION_DIR / audio_dir_name / date_str / "chroniques" / f"{cf.stem}_transcription.txt"
            transcribe_kyutai(cf, ctxt)
    else:
        print("   ⚠️ Aucun dossier 'chroniques' trouvé.")

    # 3. GÉNÉRATION TIMECODES
    print(f"\n--- [ÉTAPE] Alignement Timecodes (Estimation par texte) ---")
    
    if not integrale_txt.exists():
        print("❌ Transcription intégrale absente, impossible d'aligner.")
        sys.exit(1)
        
    with open(integrale_txt, 'r', encoding='utf-8') as f:
        main_text = f.read()
    
    main_duration = get_audio_duration(integrale_file)
    if main_duration == 0:
        print("⚠️ Impossible de déterminer la durée de l'intégrale. Les timecodes seront à 0.")
        
    results = []
    not_found = []
    
    chron_txt_dir = TRANSCRIPTION_DIR / audio_dir_name / date_str / "chroniques"
    if chron_txt_dir.exists():
        for ctxt_file in sorted(chron_txt_dir.glob("*_transcription.txt")):
            name = ctxt_file.name.replace("_transcription.txt", "")
            with open(ctxt_file, 'r', encoding='utf-8') as f:
                chron_text = f.read()
            
            start, end = find_segment_range_text(main_text, chron_text, main_duration)
            if start and end:
                results.append(f"{start} - {end} : {name}")
                print(f"   [+] Trouvé : {name}")
            else:
                not_found.append(name)
                print(f"   [-] Non trouvé : {name}")

    if results or not_found:
        output_file = OUTPUT_TIMECODE_DIR / f"{audio_dir_name}_{date_str}.txt"
        OUTPUT_TIMECODE_DIR.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as out:
            if results:
                out.write("\n".join(results) + "\n")
            if not_found:
                out.write("\n\nNON TROUVÉES :\n")
                out.write("\n".join(not_found) + "\n")
        print(f"\n✨ Fichier de timecodes créé : {output_file}")
    else:
        print("\n⚠️ Aucun résultat généré.")

if __name__ == "__main__":
    main()
