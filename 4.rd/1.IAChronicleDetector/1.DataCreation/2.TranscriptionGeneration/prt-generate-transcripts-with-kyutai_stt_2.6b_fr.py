#!/usr/bin/env python3
"""
Script de transcription audio avec Kyutai STT (MLX Version)
Optimisé pour Apple Silicon (M1/M2/M3)
Transcrit les fichiers audio et les déplace vers audio-done en cas de succès
"""

import os
import sys
import json
import shutil
import argparse
import time
from pathlib import Path
from datetime import timedelta

# Importations différées pour la rapidité du --help
# import mlx.core as mx
# import mlx.nn as nn
# import numpy as np
# import librosa
# import rustymimi
# import sentencepiece
# from huggingface_hub import hf_hub_download
# from moshi_mlx import models, utils

# Configuration par défaut
SCRIPT_DIR = Path(__file__).resolve().parent
RD_DIR = SCRIPT_DIR.parent.parent.parent
ASSETS_DIR = RD_DIR / "@assets"

DEFAULT_MEDIA_BASE_DIR = str(ASSETS_DIR / "0.media")
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = str(ASSETS_DIR / "1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr")
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit des fichiers audio avec Kyutai STT (MLX) et les déplace vers audio-done",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Chemin vers un fichier audio unique à traiter"
    )
    
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Afficher la transcription sur stdout au lieu de l'écrire dans un fichier"
    )
    
    parser.add_argument(
        "--no-srt",
        action="store_true",
        help="Générer uniquement du texte brut sans formatage SRT ni marqueurs temporels"
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
        "--hf-repo",
        type=str,
        default=DEFAULT_MODEL_ID,
        help=f"Repo Hugging Face du modèle MLX (défaut: {DEFAULT_MODEL_ID})"
    )
    
    parser.add_argument(
        "--max-files-to-process",
        type=int,
        default=None,
        help="Nombre maximum de fichiers à traiter (utile pour le test)"
    )
    
    return parser.parse_args()

def format_timestamp(seconds):
    """Convertit des secondes en format SRT (HH:MM:SS,mmm)"""
    td = timedelta(seconds=float(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def transcribe_audio_mlx(file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, no_srt=False):
    """
    Transcrit un fichier audio en utilisant MLX et rustymimi
    Retourne le contenu (SRT ou texte brut) sous forme de chaîne de caractères
    """
    import mlx.core as mx
    import numpy as np
    import librosa
    from moshi_mlx import utils
    from tqdm import tqdm
    
    try:
        # Charger l'audio et rééchantillonner à 24kHz
        audio, _ = librosa.load(file_path, sr=24000)
        
        # Padding selon la config STT (important pour l'alignement)
        if stt_config:
            pad_right_sec = stt_config.get("audio_delay_seconds", 0.0)
            pad_left_sec = stt_config.get("audio_silence_prefix_seconds", 0.0)
            pad_left = int(pad_left_sec * 24000)
            pad_right = int((pad_right_sec + 1.0) * 24000)
            audio = np.pad(audio, (pad_left, pad_right), mode="constant")
        
        steps = len(audio) // 1920
        
        # Initialiser le générateur
        from moshi_mlx.models import LmGen
        gen = LmGen(
            model=model,
            max_steps=steps + 10,
            text_sampler=utils.Sampler(temp=0.0), # Greedy pour STT
            audio_sampler=utils.Sampler(temp=0.0),
            check=False,
        )
        
        all_tokens = []
        other_codebooks = lm_config.other_codebooks
        
        # Traitement par steps de 80ms (1920 échantillons)
        file_name = os.path.basename(file_path)
        for idx in tqdm(range(steps), desc=f"   └─ {file_name[:30]}", unit="step", leave=False, file=sys.stderr):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            # rustymimi attend (batch, channels, samples) -> (1, 1, 1920)
            pcm_input = pcm_chunk[None, None, :]
            
            # Encodage Mimi
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
            
            # Step du modèle
            text_token = gen.step(other_audio_tokens_mx[0])
            text_token_id = text_token[0].item()
            
            # On stocke le token avec son timestamp (ajusté du délai audio)
            delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
            timestamp = (idx * 0.08) - delay
            if timestamp < 0: timestamp = 0
            
            all_tokens.append((timestamp, text_token_id))

        # Reconstruction du texte et SRT
        srt_entries = []
        current_text = []
        start_time = None
        
        for timestamp, token_id in all_tokens:
            if token_id in (0, 3):
                continue
                
            char = text_tokenizer.id_to_piece(token_id)
            char = char.replace(" ", " ") # Caractère spécial SentencePiece
            char = char.replace("▁", " ") # Caractère spécial Kyutai
            
            if char:
                if start_time is None and char.strip():
                    start_time = timestamp
                
                if start_time is not None:
                    current_text.append(char)
                
                if len(current_text) > 12 or any(p in char for p in ".!?"):
                    end_time = timestamp + 0.08
                    text_content = "".join(current_text).strip()
                    if text_content:
                        srt_entries.append((start_time, end_time, text_content))
                    current_text = []
                    start_time = None
        
        # Dernier segment
        if current_text and start_time is not None:
            srt_entries.append((start_time, all_tokens[-1][0] + 0.08, "".join(current_text).strip()))

        # Génération du contenu de sortie
        if no_srt:
            all_chars = []
            for _, token_id in all_tokens:
                if token_id in (0, 3): continue
                char = text_tokenizer.id_to_piece(token_id)
                char = char.replace(" ", " ")
                char = char.replace("▁", " ")
                all_chars.append(char)
            return "".join(all_chars).strip()
        else:
            srt_content = ""
            for i, (start, end, text) in enumerate(srt_entries):
                srt_content += f"{i+1}\n"
                srt_content += f"{format_timestamp(start)} --> {format_timestamp(end)}\n"
                srt_content += f"{text}\n\n"
            return srt_content
            
    except Exception as e:
        print(f"Exception lors de la transcription MLX: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None

def move_to_done(file_path, media_base_dir, audio_dir, rel_sub_dir):
    """
    Déplace un fichier audio vers audio-done
    """
    audio_done_dir = Path(media_base_dir) / "audio-done" / audio_dir / rel_sub_dir
    audio_done_dir.mkdir(parents=True, exist_ok=True)
    destination = audio_done_dir / Path(file_path).name
    try:
        shutil.move(str(file_path), str(destination))
        return True
    except Exception as e:
        print(f"   ❌ Erreur déplacement: {e}")
        return False

def main():
    args = parse_arguments()
    
    # Importations lourdes
    import mlx.core as mx
    import mlx.nn as nn
    import sentencepiece
    import rustymimi
    from tqdm import tqdm
    from huggingface_hub import hf_hub_download
    from moshi_mlx import models
    
    # Récupération des dossiers audio si pas de mode single file
    all_files = []
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ Fichier d'entrée introuvable : {args.input}", file=sys.stderr)
            return
        all_files.append((input_path, None))
    else:
        audio_base = Path(args.media_base_dir) / "audio"
        if not audio_base.exists():
            print(f"❌ Dossier source introuvable: {audio_base}", file=sys.stderr)
            return
            
        audio_dirs = sorted([d.name for d in audio_base.iterdir() if d.is_dir() and not d.name.startswith('.')])
        
        # Scan des fichiers
        AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".m4b"}
        for adir in audio_dirs:
            path = audio_base / adir
            # On ne prend que les fichiers dans un sous-répertoire 'chroniques'
            files = [f for f in path.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS and "chroniques" in f.parts]
            for f in files:
                all_files.append((f, adir))
                
    if not all_files:
        print("ℹ️ Aucun fichier à traiter.", file=sys.stderr)
        return

    # Limite si spécifiée
    if args.max_files_to_process and not args.input:
        all_files = all_files[:args.max_files_to_process]
        print(f"⚠️ Limité à {args.max_files_to_process} fichiers par l'option --max-files-to-process", file=sys.stderr)

    if not args.stdout:
        print(f"🖥️  MLX Device: GPU (Metal)", file=sys.stderr)
        print(f"📥 Chargement du modèle depuis {args.hf_repo}...", file=sys.stderr)
    
    try:
        config_path = hf_hub_download(args.hf_repo, "config.json")
        with open(config_path, "r") as f:
            config_dict = json.load(f)
            
        stt_config = config_dict.get("stt_config")
        lm_config = models.LmConfig.from_config_dict(config_dict)
        model = models.Lm(lm_config)
        model.set_dtype(mx.bfloat16)
        
        weights_path = hf_hub_download(args.hf_repo, config_dict.get("moshi_name", "model.safetensors"))
        if weights_path.endswith(".q4.safetensors"):
            nn.quantize(model, bits=4, group_size=32)
        elif weights_path.endswith(".q8.safetensors"):
            nn.quantize(model, bits=8, group_size=64)
            
        model.load_weights(weights_path)
        
        tokenizer_path = hf_hub_download(args.hf_repo, config_dict["tokenizer_name"])
        text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
        
        mimi_path = hf_hub_download(args.hf_repo, config_dict["mimi_name"])
        audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
        
        model.warmup()
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return

    if not args.stdout:
        print(f"🚀 Traitement de {len(all_files)} fichiers...", file=sys.stderr)
    
    # On désactive la barre de progression globale si on a un seul fichier ou si on est en mode stdout
    disable_pbar = args.stdout or len(all_files) == 1
    
    with tqdm(total=len(all_files), unit="file", desc="Transcription MLX", disable=disable_pbar, file=sys.stderr) as pbar:
        for file_path, adir in all_files:
            srt_content = transcribe_audio_mlx(
                file_path, 
                model, 
                audio_tokenizer, 
                text_tokenizer, 
                lm_config, 
                stt_config,
                no_srt=args.no_srt
            )
            
            if srt_content:
                if args.stdout:
                    print(srt_content)
                else:
                    # Déterminer le chemin de sortie
                    if adir:
                        audio_path = Path(args.media_base_dir) / "audio" / adir
                        rel_path = file_path.relative_to(audio_path).parent
                        output_dir = Path(args.transcription_output_dir) / adir / rel_path
                    else:
                        output_dir = Path(args.transcription_output_dir)
                    
                    output_dir.mkdir(parents=True, exist_ok=True)
                    ext = ".txt" if args.no_srt else ".srt"
                    output_file = output_dir / f"{file_path.stem}_transcription{ext}"
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    
                    if not args.no_move_to_done_when_processed and adir:
                        move_to_done(file_path, args.media_base_dir, adir, rel_path)
            else:
                if not args.stdout:
                    tqdm.write(f"❌ Échec pour {file_path.name}", file=sys.stderr)
            
            if not disable_pbar:
                pbar.set_postfix_str(f"Fichier: {file_path.name[:20]}")
                pbar.update(1)

if __name__ == "__main__":
    main()
