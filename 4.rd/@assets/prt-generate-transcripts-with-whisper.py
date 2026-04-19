#!/usr/bin/env python3
"""
Script de transcription audio avec Whisper.cpp
Transcrit les fichiers audio et les déplace vers audio-done en cas de succès
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

# Configuration par défaut
DEFAULT_MEDIA_BASE_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/0.media"
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo"
DEFAULT_WHISPER_CLI_PATH = "/opt/homebrew/bin/whisper-cli"
DEFAULT_MODEL_PATH = "/Applications/DevTools/AI/whisper.cpp/models/ggml-large-v3-turbo.bin"

# Répertoires audio à traiter
AUDIO_DIRS = [
    "0.france-inter-grande-matinale",
    "1.misc",
    "2.rtl-matin",
    "3.franceinfo-matin",
    "4.franceculture-matin"
]

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit des fichiers audio avec Whisper.cpp et les déplace vers audio-done",
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
        "--whisper-cli-path",
        type=str,
        default=DEFAULT_WHISPER_CLI_PATH,
        help=f"Chemin vers l'exécutable whisper-cli (défaut: {DEFAULT_WHISPER_CLI_PATH})"
    )
    
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Chemin vers le modèle Whisper (défaut: {DEFAULT_MODEL_PATH})"
    )
    
    return parser.parse_args()

def display_configuration(args):
    """Affiche la configuration utilisée"""
    print("")
    print(" Paramètres utilisés de prt-generate-transcripts-with-whisper")
    print("-" * 45)
    print("")
    print(f"  Media base directory:     [{args.media_base_dir}]")
    print(f"  Transcription output dir: [{args.transcription_output_dir}]")
    print(f"  Whisper CLI path:         [{args.whisper_cli_path}]")
    print(f"  Model path:               [{args.model_path}]")
    print(f"  Move to audio-done:       [{'Non' if args.no_move_to_done_when_processed else 'Oui'}]")
    print(f"  Dossiers à traiter:       [{', '.join(AUDIO_DIRS)}]")
    print("-" * 60)
    print("")
    print("💡 Utilisez --help pour voir tous les paramètres disponibles\n")
    print("")
    
    # Vérification de l'existence des chemins critiques
    if not os.path.exists(args.whisper_cli_path):
        print(f"⚠️  Attention: whisper-cli introuvable au chemin indiqué: {args.whisper_cli_path}")
    
    if not os.path.exists(args.model_path):
        print(f"⚠️  Attention: modèle introuvable au chemin indiqué: {args.model_path}")
    
    if not os.path.exists(args.media_base_dir):
        print(f"⚠️  Attention: répertoire média introuvable: {args.media_base_dir}")
    print()

def transcribe_audio(file_path, output_path, whisper_cli_path, model_path):
    """
    Transcrit un fichier audio avec whisper-cli
    Retourne True si succès, False sinon
    """
    cmd = [
        whisper_cli_path,
        "-m", model_path,
        "-f", file_path
    ]
    
    try:
        with open(output_path, 'w') as output_file:
            result = subprocess.run(
                cmd,
                stdout=output_file,
                stderr=subprocess.PIPE,
                text=True
            )
        
        if result.returncode == 0:
            return True
        else:
            # En cas d'erreur, on supprime le fichier de sortie partiellement créé
            if os.path.exists(output_path):
                os.remove(output_path)
            print(f"Erreur whisper-cli: {result.stderr[:200]}...")
            return False
            
    except Exception as e:
        print(f"Exception lors de l'exécution de whisper-cli: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def move_to_done(file_path, media_base_dir, audio_dir):
    """
    Déplace un fichier audio vers audio-done
    Retourne True si succès, False sinon
    """
    audio_done_dir = Path(media_base_dir) / "audio-done" / audio_dir
    audio_done_dir.mkdir(parents=True, exist_ok=True)
    
    destination = audio_done_dir / Path(file_path).name
    
    try:
        shutil.move(str(file_path), str(destination))
        print(f"   📦 Fichier déplacé vers: {destination}")
        return True
    except Exception as e:
        print(f"   ❌ Erreur lors du déplacement: {e}")
        return False

def process_audio_files(args):
    """Parcourt les répertoires et traite les fichiers audio"""
    
    stats = {
        "total_files": 0,
        "transcribed_success": 0,
        "transcribed_failed": 0,
        "moved_success": 0,
        "moved_failed": 0
    }
    
    for audio_dir in AUDIO_DIRS:
        print(f"\n📂 Traitement du dossier: {audio_dir}")
        
        audio_path = Path(args.media_base_dir) / "audio" / audio_dir
        output_dir = Path(args.transcription_output_dir) / audio_dir
        
        # Vérifier si le répertoire source existe
        if not audio_path.exists():
            print(f"   ⚠️  Répertoire source inexistant: {audio_path}")
            continue
        
        # Créer le répertoire de sortie
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Lister les fichiers audio (tous les fichiers, pas de sous-répertoires)
        files = [f for f in audio_path.iterdir() if f.is_file()]
        
        if not files:
            print(f"   ℹ️  Aucun fichier trouvé dans {audio_dir}")
            continue
        
        stats["total_files"] += len(files)
        
        for file_path in files:
            print(f"\n   🎵 Fichier: {file_path.name}")
            
            # Préparer le nom du fichier de sortie
            base_name = file_path.stem  # sans extension
            output_file = output_dir / f"{base_name}_transcription.srt"
            
            # Transcription
            print(f"   🔄 Transcription en cours...")
            success = transcribe_audio(
                str(file_path),
                str(output_file),
                args.whisper_cli_path,
                args.model_path
            )
            
            if success:
                stats["transcribed_success"] += 1
                print(f"   ✅ Transcription sauvegardée: {output_file}")
                
                # Déplacement vers audio-done (sauf si désactivé)
                if not args.no_move_to_done_when_processed:
                    if move_to_done(file_path, args.media_base_dir, audio_dir):
                        stats["moved_success"] += 1
                    else:
                        stats["moved_failed"] += 1
                else:
                    print(f"   ⏸️  Déplacement désactivé (--no-move-to-done-when-processed)")
            else:
                stats["transcribed_failed"] += 1
                print(f"   ❌ Échec de la transcription pour {file_path.name}")
    
    return stats

def display_stats(stats):
    """Affiche les statistiques finales"""
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU TRAITEMENT")
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
    global args
    args = parse_arguments()
    
    display_configuration(args)
    
    print("🚀 Démarrage du traitement des transcriptions...\n")
    
    stats = process_audio_files(args)
    
    display_stats(stats)
    
    if stats['transcribed_failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()

