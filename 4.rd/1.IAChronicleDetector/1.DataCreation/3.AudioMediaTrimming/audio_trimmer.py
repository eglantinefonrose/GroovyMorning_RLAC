import argparse
import os
import re
import sys
from pathlib import Path
from pydub import AudioSegment

# Seuil de 2 minutes en millisecondes
GAP_THRESHOLD_MS = 2 * 60 * 1000

def parse_timecode(tc_str):
    """Convertit [HH:MM:SS:mmm] ou [HH:MM:SS.mmm] en millisecondes."""
    tc_str = tc_str.strip("[] ")
    # On gère les formats avec . ou : pour les millisecondes
    match = re.match(r'(\d+):(\d+):(\d+)[:.](\d+)', tc_str)
    if match:
        h, m, s, ms = map(int, match.groups())
        return ((h * 3600 + m * 60 + s) * 1000) + ms
    
    # Fallback pour HH:MM:SS sans millisecondes
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
        # On ignore tout ce qui est dans un dossier nommé 'chroniques'
        if 'chroniques' in Path(root).parts:
            continue
        for file in files:
            if file.lower().endswith(('.mp3', '.m4a')) and not file.endswith('_trimmed' + Path(file).suffix):
                return Path(root) / file
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Script de trimming audio basé sur des gaps de timecodes.",
        usage="python %(prog)s <nom_dossier> <nom_radio>"
    )
    parser.add_argument("nom_dossier", help="Nom du dossier spécifique à traiter")
    parser.add_argument("nom_radio", help="Nom de la radio")
    args = parser.parse_args()

    nom_dossier = args.nom_dossier
    nom_radio = args.nom_radio

    # Localisation des racines de projet
    current_dir = Path.cwd().absolute()
    assets_root = None
    # On cherche @assets en remontant les parents
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "@assets").exists():
            assets_root = parent / "@assets"
            break
    
    if not assets_root:
        # Fallback sur le chemin relatif spécifié par défaut
        assets_root = (current_dir / "../../../@assets").resolve()

    media_root = assets_root / "0.media"
    # Le prompt spécifie le dossier de base des timecodes
    timecode_base_root = assets_root / "2.humanOutputs" / "1.timecode-segments" / "2.audio-analyse" / "timecode_chroniques"

    # Vérification initiale
    if not media_root.exists():
        print(f"Erreur : Le dossier 0.media est introuvable à {media_root}")
        sys.exit(1)
    
    # 1. Vérification que <nom_radio> existe dans l'arborescence des timecodes
    # Le prompt dit : .../timecode_chroniques/<nom_radio>
    # Mais aussi : sous-dossier ... un niveau en dessous de 1.rtl-matin
    # On va essayer les deux
    radio_timecode_dir = timecode_base_root / nom_radio
    if not radio_timecode_dir.exists():
        # Essai avec 1.rtl-matin
        radio_timecode_dir = timecode_base_root / "1.rtl-matin" / nom_radio
    
    if not radio_timecode_dir.exists():
        # Dernier recours : recherche récursive dans timecode_chroniques
        found = False
        for p in timecode_base_root.rglob(nom_radio):
            if p.is_dir():
                radio_timecode_dir = p
                found = True
                break
        if not found:
            print(f"Erreur : Le dossier de radio '{nom_radio}' est introuvable dans {timecode_base_root}")
            sys.exit(1)

    # 2. Vérification que <nom_dossier> existe dans 0.media
    # On cherche media_root/**/<nom_radio>/<nom_dossier>
    target_media_dir = None
    # On cherche d'abord selon la hiérarchie suggérée
    search_paths = [
        media_root / "audio" / "1.rtl-matin" / nom_radio / nom_dossier,
        media_root / "audio" / nom_radio / nom_dossier,
        media_root / nom_radio / nom_dossier
    ]
    for p in search_paths:
        if p.exists() and p.is_dir():
            target_media_dir = p
            break
    
    if not target_media_dir:
        # Recherche récursive si non trouvé directement
        for p in media_root.rglob(nom_dossier):
            if p.is_dir() and nom_radio in str(p):
                target_media_dir = p
                break
    
    if not target_media_dir:
        print(f"Erreur : Le dossier '{nom_dossier}' pour la radio '{nom_radio}' est introuvable dans {media_root}")
        sys.exit(1)

    # Collecte du fichier audio
    audio_file = find_audio_file(target_media_dir)
    if not audio_file:
        print(f"Erreur : Aucun fichier audio (.mp3, .m4a) trouvé dans {target_media_dir} (hors dossiers 'chroniques')")
        sys.exit(1)
    
    nom_du_dossier_du_mp3 = audio_file.parent.name
    print(f"Fichier audio sélectionné : {audio_file}")

    # 3. Recherche du fichier de timecodes
    timecode_file = None
    suffix_pattern = f"timecode_chroniques_{nom_du_dossier_du_mp3}.txt"
    for root, dirs, files in os.walk(radio_timecode_dir):
        # Ignore le dossier news
        if 'news' in Path(root).parts:
            continue
        for file in files:
            if file.endswith(suffix_pattern):
                timecode_file = Path(root) / file
                break
        if timecode_file:
            break
    
    if not timecode_file:
        print(f"Erreur : Aucun fichier de timecode se terminant par '{suffix_pattern}' trouvé dans {radio_timecode_dir}")
        sys.exit(1)
    
    print(f"Fichier de timecode sélectionné : {timecode_file}")

    # 4. Traitement Audio
    print("Chargement du fichier audio en cours...")
    try:
        audio = AudioSegment.from_file(str(audio_file))
    except Exception as e:
        print(f"Erreur lors du chargement de l'audio : {e}")
        sys.exit(1)

    segments = []
    try:
        with open(timecode_file, 'r', encoding='utf-8') as f:
            for line in f:
                # On capture les deux timecodes et tout ce qui suit
                match = re.search(r'(\[.*?\])\s*-\s*(\[.*?\])(.*)', line)
                if match:
                    try:
                        start = parse_timecode(match.group(1))
                        end = parse_timecode(match.group(2))
                        name = match.group(3).strip()
                        segments.append((start, end, name))
                    except ValueError as ve:
                        print(f"Avertissement : Ligne de timecode ignorée : {line.strip()} ({ve})")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier de timecode : {e}")
        sys.exit(1)

    if not segments:
        print("Erreur : Aucun segment valide trouvé dans le fichier de timecode.")
        sys.exit(1)

    segments.sort()

    # Logique de reconstruction
    final_audio = AudioSegment.empty()
    new_segments_tc = []
    current_out_ms = 0
    cuts_count = 0
    ignored_count = 0

    for i in range(len(segments)):
        start, end, name = segments[i]
        
        # Gestion du gap entre le segment précédent et celui-ci
        if i > 0:
            prev_end = segments[i-1][1]
            gap_ms = start - prev_end
            
            if gap_ms > GAP_THRESHOLD_MS:
                # Portion supprimée
                cuts_count += 1
                # print(f"  Gap > 2min détecté ({gap_ms/1000:.1f}s) -> supprimé.")
            else:
                # Portion conservée car < 2 mins
                if gap_ms > 0:
                    gap_audio = audio[prev_end:start]
                    final_audio += gap_audio
                    current_out_ms += len(gap_audio)
                elif gap_ms < 0:
                    print(f"Avertissement : Segments chevauchants détectés à {format_timecode(start)}")
        
        # Ajout du segment lui-même
        seg_audio = audio[start:end]
        new_start = current_out_ms
        final_audio += seg_audio
        current_out_ms += len(seg_audio)
        new_segments_tc.append((new_start, current_out_ms, name))

    # 5. Export
    output_audio_path = audio_file.parent / f"{audio_file.stem}_trimmed{audio_file.suffix}"
    print(f"Export de l'audio trimé : {output_audio_path.name}")
    try:
        # Extraction du format depuis l'extension
        fmt = audio_file.suffix.lower().strip('.')
        if fmt == 'm4a':
            fmt = 'ipod' # pydub/ffmpeg utilise ipod pour m4a souvent, ou simplement m4a
        final_audio.export(str(output_audio_path), format=fmt if fmt != 'm4a' else 'mp4')
    except Exception as e:
        print(f"Erreur lors de l'export audio : {e}")
        sys.exit(1)

    # Mise à jour des timecodes
    news_dir = radio_timecode_dir / "news"
    news_dir.mkdir(exist_ok=True)
    output_tc_path = news_dir / f"{audio_file.stem}_new_from_audio.txt"
    
    print(f"Génération des nouveaux timecodes : {output_tc_path}")
    try:
        with open(output_tc_path, 'w', encoding='utf-8') as f:
            for ns, ne, name in new_segments_tc:
                suffix = f" {name}" if name else ""
                f.write(f"{format_timecode(ns)} - {format_timecode(ne)}{suffix}\n")
    except Exception as e:
        print(f"Erreur lors de l'écriture des nouveaux timecodes : {e}")

    # 6. Résumé
    print("\n" + "="*40)
    print("RÉSUMÉ DE L'EXÉCUTION")
    print("="*40)
    print(f"Fichiers traités : 1 ({audio_file.name})")
    print(f"Coupures effectuées (gaps > 2min) : {cuts_count}")
    print(f"Segments conservés : {len(segments)}")
    print(f"Durée originale : {format_timecode(len(audio))}")
    print(f"Nouvelle durée : {format_timecode(len(final_audio))}")
    print(f"Audio sauvegardé : {output_audio_path.name}")
    print(f"Timecodes sauvegardés : {output_tc_path}")
    print("="*40)

if __name__ == "__main__":
    main()
