#!/usr/bin/env python3
"""
Script de transcription audio avec Kyutai STT (stt-1b-en_fr)
Transcrit les fichiers audio et les déplace vers audio-done en cas de succès
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path
from datetime import timedelta

# Importations différées pour ne pas ralentir le démarrage si on ne fait que l'aide
# import torch
# import librosa
# from transformers import KyutaiSpeechToTextProcessor, KyutaiSpeechToTextForConditionalGeneration

# Configuration par défaut
DEFAULT_MEDIA_BASE_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/0.media"
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-trfs"

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit des fichiers audio avec Kyutai STT et les déplace vers audio-done",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s                                    # Exécute avec les paramètres par défaut
  %(prog)s --no-move-to-done-when-processed   # Transcrit sans déplacer les fichiers
  %(prog)s --media-base-dir /chemin/perso     # Utilise un répertoire média personnalisé
        """
    )
    
    parser.add_argument(
        "--no-move-to-done-when-processed",
        action="store_true",
        help="Ne pas déplacer les fichiers vers audio-done après transcription réussie"
    )
    
    parser.add_argument(
        "--media-base-dir",
        type=str,
        default=DEFAULT_MEDIA_BASE_DIR,
        help=f"Répertoire racine des médias (défaut: {DEFAULT_MEDIA_BASE_DIR})"
    )
    
    parser.add_argument(
        "--transcription-output-dir",
        type=str,
        default=DEFAULT_TRANSCRIPTION_OUTPUT_DIR,
        help=f"Répertoire de sortie des transcriptions (défaut: {DEFAULT_TRANSCRIPTION_OUTPUT_DIR})"
    )
    
    parser.add_argument(
        "--model-id",
        type=str,
        default=DEFAULT_MODEL_ID,
        help=f"ID du modèle Hugging Face (défaut: {DEFAULT_MODEL_ID})"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device à utiliser (cpu, cuda, mps). Par défaut, détecte automatiquement."
    )
    
    return parser.parse_args()

def display_configuration(args, audio_dirs):
    """Affiche la configuration utilisée"""
    print("")
    print(" Paramètres utilisés de prt-generate-transcripts-with-kyutai")
    print("-" * 65)
    print("")
    print(f"  Media base directory:     [{args.media_base_dir}]")
    print(f"  Transcription output dir: [{args.transcription_output_dir}]")
    print(f"  Model ID:                 [{args.model_id}]")
    print(f"  Device:                   [{args.device or 'auto'}]")
    print(f"  Move to audio-done:       [{'Non' if args.no_move_to_done_when_processed else 'Oui'}]")
    print(f"  Dossiers détectés:        [{len(audio_dirs)} dossiers dans audio/]")
    print("-" * 65)
    print("")
    print("💡 Utilisez --help pour voir tous les paramètres disponibles\n")
    print("")
    
    if not os.path.exists(args.media_base_dir):
        print(f"⚠️  Attention: répertoire média introuvable: {args.media_base_dir}")
    print()

def format_timestamp(seconds):
    """Convertit des secondes en format SRT (HH:MM:SS,mmm)"""
    td = timedelta(seconds=float(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt(transcription_with_timestamps):
    """
    Convertit la sortie brute du modèle avec tags <|timestamp|> en format SRT
    """
    # Pattern pour extraire les timestamps et le texte
    tokens = re.split(r"(<\|\d+\.\d+\|>)", transcription_with_timestamps)
    
    srt_entries = []
    current_start = None
    current_text = ""
    
    for token in tokens:
        if not token:
            continue
        
        ts_match = re.match(r"<\|(\d+\.\d+)\|>", token)
        if ts_match:
            ts = ts_match.group(1)
            if current_start is not None:
                if current_text.strip():
                    srt_entries.append((current_start, ts, current_text.strip()))
                current_text = ""
            current_start = ts
        else:
            current_text += token
            
    srt_content = ""
    for i, (start, end, text) in enumerate(srt_entries):
        start_str = format_timestamp(start)
        end_str = format_timestamp(end)
        srt_content += f"{i+1}\n{start_str} --> {end_str}\n{text}\n\n"
        
    return srt_content

def transcribe_audio(file_path, output_path, model, processor, device):
    """
    Transcrit un fichier audio avec Kyutai STT via transformers
    Retourne True si succès, False sinon
    """
    import torch
    import librosa
    
    try:
        audio, _ = librosa.load(file_path, sr=24000)
        inputs = processor(audio, sampling_rate=24000, return_tensors="pt").to(device)
        
        with torch.no_grad():
            output_tokens = model.generate(**inputs, return_timestamps=True)
        
        prediction = processor.batch_decode(output_tokens, skip_special_tokens=False)[0]
        srt_content = generate_srt(prediction)
        
        if not srt_content:
            text = processor.batch_decode(output_tokens, skip_special_tokens=True)[0]
            srt_content = f"1\n00:00:00,000 --> 00:00:10,000\n{text}\n"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        return True
            
    except Exception as e:
        print(f"Exception lors de la transcription: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def move_to_done(file_path, media_base_dir, audio_dir, rel_sub_dir):
    """
    Déplace un fichier audio vers audio-done en préservant la structure des sous-dossiers
    """
    audio_done_dir = Path(media_base_dir) / "audio-done" / audio_dir / rel_sub_dir
    audio_done_dir.mkdir(parents=True, exist_ok=True)
    
    destination = audio_done_dir / Path(file_path).name
    
    try:
        shutil.move(str(file_path), str(destination))
        print(f"   📦 Fichier déplacé vers: {destination}")
        return True
    except Exception as e:
        print(f"   ❌ Erreur lors du déplacement: {e}")
        return False

def process_audio_files(args, model, processor, device, audio_dirs):
    """Parcourt les répertoires récursivement et traite les fichiers audio"""
    from tqdm import tqdm
    import time
    
    # Extensions audio supportées
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".m4b"}
    
    # Phase 1: Scan de tous les fichiers à traiter
    print("🔍 Scan des fichiers en cours...")
    all_files_to_process = []
    total_size_bytes = 0
    
    for audio_dir in audio_dirs:
        audio_path = Path(args.media_base_dir) / "audio" / audio_dir
        if not audio_path.exists():
            continue
            
        files = [
            f for f in audio_path.rglob("*") 
            if f.is_file() and not f.name.startswith('.') and f.suffix.lower() in AUDIO_EXTENSIONS
        ]
        
        for f in files:
            file_size = f.stat().st_size
            all_files_to_process.append((f, audio_dir, file_size))
            total_size_bytes += file_size
            
    total_files = len(all_files_to_process)
    if total_files == 0:
        print("ℹ️ Aucun fichier trouvé à traiter.")
        return {
            "total_files": 0,
            "transcribed_success": 0,
            "transcribed_failed": 0,
            "moved_success": 0,
            "moved_failed": 0
        }
        
    print(f"📊 {total_files} fichiers trouvés ({total_size_bytes / (1024*1024):.1f} Mo)")
    print("🚀 Démarrage du traitement...")
    
    stats = {
        "total_files": total_files,
        "transcribed_success": 0,
        "transcribed_failed": 0,
        "moved_success": 0,
        "moved_failed": 0
    }
    
    # Phase 2: Traitement avec barre de progression
    # On utilise tqdm avec l'unité 'file'
    with tqdm(total=total_files, unit="file", desc="Progression globale") as pbar:
        for file_path, audio_dir, _ in all_files_to_process:
            audio_path = Path(args.media_base_dir) / "audio" / audio_dir
            rel_sub_dir = file_path.relative_to(audio_path).parent
            display_name = file_path.relative_to(audio_path)
            
            # Mise à jour de la description pour voir le fichier actuel sans polluer la sortie
            pbar.set_postfix_str(f"Dernier: {file_path.name[:20]}...")
            
            output_dir = Path(args.transcription_output_dir) / audio_dir / rel_sub_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = file_path.stem
            output_file = output_dir / f"{base_name}_transcription.srt"
            
            success = transcribe_audio(
                str(file_path),
                str(output_file),
                model,
                processor,
                device
            )
            
            if success:
                stats["transcribed_success"] += 1
                
                if not args.no_move_to_done_when_processed:
                    if move_to_done(file_path, args.media_base_dir, audio_dir, rel_sub_dir):
                        stats["moved_success"] += 1
                    else:
                        stats["moved_failed"] += 1
            else:
                stats["transcribed_failed"] += 1
                # En cas d'échec, on l'affiche explicitement au dessus de la barre
                tqdm.write(f"❌ Échec de la transcription pour {file_path.name}")
            
            pbar.update(1)
    
    return stats

def get_audio_subdirs(media_base_dir):
    """Récupère la liste des dossiers dans le répertoire audio/"""
    audio_path = Path(media_base_dir) / "audio"
    if not audio_path.exists():
        return []
    # Liste uniquement les dossiers directs dans audio/
    return sorted([d.name for d in audio_path.iterdir() if d.is_dir() and not d.name.startswith('.')])

def display_stats(stats, args):
    """Affiche les statistiques finales"""
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU TRAITEMENT (KYUTAI)")
    print("=" * 60)
    print(f"📊 Total fichiers trouvés:     {stats['total_files']}")
    print(f"✅ Transcriptions réussies:    {stats['transcribed_success']}")
    print(f"❌ Transcriptions échouées:    {stats['transcribed_failed']}")
    if not args.no_move_to_done_when_processed:
        print(f"📦 Déplacements réussis:       {stats['moved_success']}")
        print(f"⚠️  Déplacements échoués:       {stats['moved_failed']}")
    print("=" * 60)

def main():
    """Fonction principale"""
    args = parse_arguments()
    
    # Détection dynamique des dossiers à traiter
    audio_dirs = get_audio_subdirs(args.media_base_dir)
    
    display_configuration(args, audio_dirs)
    
    if not audio_dirs:
        print("❌ Aucun dossier trouvé dans le répertoire audio. Fin du script.")
        sys.exit(0)
    
    # Importations lourdes
    print("📦 Chargement des bibliothèques AI (torch, transformers)...")
    import torch
    from transformers import KyutaiSpeechToTextProcessor, KyutaiSpeechToTextForConditionalGeneration
    
    # Détection du device
    if args.device:
        device = args.device
    elif torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    
    print(f"🖥️  Utilisation du device: {device}")
    
    # Chargement du modèle
    print(f"📥 Chargement du modèle {args.model_id}...")
    try:
        processor = KyutaiSpeechToTextProcessor.from_pretrained(args.model_id)
        model = KyutaiSpeechToTextForConditionalGeneration.from_pretrained(
            args.model_id, 
            torch_dtype=torch.float16 if device != "cpu" else torch.float32,
            device_map=device
        )
    except Exception as e:
        print(f"❌ Erreur lors du chargement du modèle: {e}")
        sys.exit(1)
    
    print("🚀 Démarrage du traitement des transcriptions...\n")
    
    stats = process_audio_files(args, model, processor, device, audio_dirs)
    
    display_stats(stats, args)
    
    if stats['transcribed_failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
