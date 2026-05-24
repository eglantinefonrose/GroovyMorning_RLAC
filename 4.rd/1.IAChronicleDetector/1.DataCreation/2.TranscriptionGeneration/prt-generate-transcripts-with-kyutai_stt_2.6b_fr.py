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
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt-1b-en_fr"
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr"

# Répertoires audio à traiter
AUDIO_DIRS = [
    "1.rtl-matin",
    "2.franceinfo-matin",
    "3.franceculture-matin",
    "4.franceinter-matin"
]

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

def display_configuration(args):
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
    print(f"  Dossiers à traiter:       [{', '.join(AUDIO_DIRS)}]")
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
    # Le modèle peut renvoyer des trucs comme <|0.00|> Bonjour <|1.20|> comment <|2.00|> allez-vous ? <|3.00|>
    # On va découper par timestamps
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
                # On a un début et une fin
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
        # Charger l'audio (Kyutai nécessite 24kHz)
        audio, _ = librosa.load(file_path, sr=24000)
        
        # Préparer les inputs
        inputs = processor(audio, sampling_rate=24000, return_tensors="pt").to(device)
        
        # Générer avec timestamps
        with torch.no_grad():
            output_tokens = model.generate(**inputs, return_timestamps=True)
        
        # Décoder
        prediction = processor.batch_decode(output_tokens, skip_special_tokens=False)[0]
        
        # Convertir en SRT
        srt_content = generate_srt(prediction)
        
        # Si le SRT est vide (pas de timestamps trouvés), on met au moins le texte brut
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

def process_audio_files(args, model, processor, device):
    """Parcourt les répertoires récursivement et traite les fichiers audio"""
    
    stats = {
        "total_files": 0,
        "transcribed_success": 0,
        "transcribed_failed": 0,
        "moved_success": 0,
        "moved_failed": 0
    }
    
    # Extensions audio supportées
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".m4b"}
    
    for audio_dir in AUDIO_DIRS:
        print(f"\n📂 Traitement (récursif) du dossier: {audio_dir}")
        
        audio_path = Path(args.media_base_dir) / "audio" / audio_dir
        
        if not audio_path.exists():
            print(f"   ⚠️  Répertoire source inexistant: {audio_path}")
            continue
        
        files = [
            f for f in audio_path.rglob("*") 
            if f.is_file() and not f.name.startswith('.') and f.suffix.lower() in AUDIO_EXTENSIONS
        ]
        
        if not files:
            print(f"   ℹ️  Aucun fichier trouvé dans {audio_dir}")
            continue
        
        stats["total_files"] += len(files)
        
        for file_path in files:
            rel_sub_dir = file_path.relative_to(audio_path).parent
            display_name = file_path.relative_to(audio_path)
            
            print(f"\n   🎵 Fichier: {display_name}")
            
            output_dir = Path(args.transcription_output_dir) / audio_dir / rel_sub_dir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = file_path.stem
            output_file = output_dir / f"{base_name}_transcription.srt"
            
            print(f"   🔄 Transcription en cours (Kyutai STT)...")
            success = transcribe_audio(
                str(file_path),
                str(output_file),
                model,
                processor,
                device
            )
            
            if success:
                stats["transcribed_success"] += 1
                print(f"   ✅ Transcription sauvegardée: {output_file}")
                
                if not args.no_move_to_done_when_processed:
                    if move_to_done(file_path, args.media_base_dir, audio_dir, rel_sub_dir):
                        stats["moved_success"] += 1
                    else:
                        stats["moved_failed"] += 1
                else:
                    print(f"   ⏸️  Déplacement désactivé")
            else:
                stats["transcribed_failed"] += 1
                print(f"   ❌ Échec de la transcription pour {file_path.name}")
    
    return stats

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
    
    display_configuration(args)
    
    # Importations lourdes ici
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
    
    stats = process_audio_files(args, model, processor, device)
    
    display_stats(stats, args)
    
    if stats['transcribed_failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
