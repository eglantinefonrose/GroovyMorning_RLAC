#!/usr/bin/env python3
"""
Script de transcription audio avec Kyutai STT (MLX Version)
Optimisé pour Apple Silicon (M1/M2/M3)
Transcrit les 10 premières et 10 dernières secondes des fichiers audio
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import timedelta

# Configuration par défaut
DEFAULT_MEDIA_BASE_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/0.media"
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit le début (10s) et la fin (10s) des fichiers audio avec Kyutai STT (MLX)",
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
    
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Durée à transcrire au début et à la fin (défaut: 10.0s)"
    )
    
    return parser.parse_args()

def format_timestamp(seconds, offset_seconds=0):
    """Convertit des secondes en format SRT (HH:MM:SS,mmm) avec un décalage optionnel"""
    td = timedelta(seconds=float(seconds + offset_seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def transcribe_segment(file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, 
                      offset=0, duration=10, no_srt=False):
    """
    Transcrit un segment spécifique d'un fichier audio
    """
    import mlx.core as mx
    import numpy as np
    import librosa
    from moshi_mlx import utils
    
    try:
        # Reset des caches du modèle et du tokenizer
        if hasattr(audio_tokenizer, "reset"):
            audio_tokenizer.reset()
            
        if hasattr(model, "transformer_cache"):
            for c in model.transformer_cache:
                c.reset()
        
        if hasattr(model, "depformer_cache"):
            for c in model.depformer_cache:
                c.reset()

        # Charger le segment audio
        audio, _ = librosa.load(file_path, sr=24000, offset=offset, duration=duration)
        
        # Padding selon la config STT
        if stt_config:
            pad_right_sec = stt_config.get("audio_delay_seconds", 0.0)
            pad_left_sec = stt_config.get("audio_silence_prefix_seconds", 0.0)
            pad_left = int(pad_left_sec * 24000)
            pad_right = int((pad_right_sec + 1.0) * 24000)
            audio = np.pad(audio, (pad_left, pad_right), mode="constant")
        
        steps = len(audio) // 1920
        
        from moshi_mlx.models import LmGen
        gen = LmGen(
            model=model,
            max_steps=steps + 10,
            text_sampler=utils.Sampler(temp=0.0),
            audio_sampler=utils.Sampler(temp=0.0),
            check=False,
        )
        
        all_tokens = []
        other_codebooks = lm_config.other_codebooks
        
        for idx in range(steps):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            pcm_input = pcm_chunk[None, None, :]
            
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
            
            text_token = gen.step(other_audio_tokens_mx[0])
            text_token_id = text_token[0].item()
            
            # Forcer l évaluation pour éviter l accumulation du graphe
            mx.eval(gen.gen_sequence)
            
            delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
            timestamp = (idx * 0.08) - delay
            if timestamp < 0: timestamp = 0
            
            all_tokens.append((timestamp, text_token_id))

        if not all_tokens:
            return ""

        srt_entries = []
        current_text = []
        start_time = None
        
        for timestamp, token_id in all_tokens:
            if token_id in (0, 3): continue
                
            char = text_tokenizer.id_to_piece(token_id)
            char = char.replace(" ", " ")
            char = char.replace("▁", " ")
            
            if char:
                if start_time is None and char.strip():
                    start_time = timestamp
                
                if start_time is not None:
                    current_text.append(char)
                
                # Détection de fin de phrase ou segment
                if len(current_text) > 15 or any(p in char for p in ".!?"):
                    end_time = timestamp + 0.08
                    text_content = "".join(current_text).strip()
                    if text_content:
                        srt_entries.append((start_time, end_time, text_content))
                    current_text = []
                    start_time = None
        
        if current_text and start_time is not None:
            srt_entries.append((start_time, all_tokens[-1][0] + 0.08, "".join(current_text).strip()))

        if no_srt:
            # Un retour à la ligne par phrase détectée
            return "\n".join([text for _, _, text in srt_entries])
        else:
            srt_content = ""
            for i, (start, end, text) in enumerate(srt_entries):
                srt_content += f"{i+1}\n"
                srt_content += f"{format_timestamp(start, offset)} --> {format_timestamp(end, offset)}\n"
                srt_content += f"{text}\n\n"
            return srt_content
            
    except Exception as e:
        print(f"Exception lors de la transcription du segment (offset={offset}): {e}", file=sys.stderr)
        return None

def move_to_done(file_path, media_base_dir, audio_dir, rel_sub_dir):
    """Déplace un fichier audio vers audio-done"""
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
    
    import mlx.core as mx
    import mlx.nn as nn
    import sentencepiece
    import rustymimi
    import librosa
    from tqdm import tqdm
    from huggingface_hub import hf_hub_download
    from moshi_mlx import models
    
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

    if args.max_files_to_process and not args.input:
        all_files = all_files[:args.max_files_to_process]
        print(f"⚠️ Limité à {args.max_files_to_process} fichiers", file=sys.stderr)

    if not args.stdout:
        print(f"🖥️  MLX Device: GPU (Metal)", file=sys.stderr)
        print(f"📥 Chargement du modèle {args.hf_repo}...", file=sys.stderr)
    
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
        print(f"❌ Erreur initialisation: {e}", file=sys.stderr)
        return

    if not args.stdout:
        print(f"🚀 Traitement de {len(all_files)} fichiers (début et fin)...", file=sys.stderr)
    
    disable_pbar = args.stdout or len(all_files) == 1
    
    with tqdm(total=len(all_files), unit="file", desc="Transcription", disable=disable_pbar, file=sys.stderr) as pbar:
        processed_count = 0
        for file_path, adir in all_files:
            # Re-initialisation périodique pour éviter l'accumulation d'erreurs d'indexation (Metal/MLX)
            if processed_count > 0 and processed_count % 10 == 0:
                try:
                    import gc
                    audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
                    mx.metal.clear_cache()
                    gc.collect()
                except Exception as e:
                    print(f"⚠️ Erreur lors de la re-initialisation périodique: {e}", file=sys.stderr)

            try:
                # Vérifier si les fichiers de sortie existent déjà pour passer
                if not args.stdout:
                    if adir:
                        audio_path = Path(args.media_base_dir) / "audio" / adir
                        rel_path = file_path.relative_to(audio_path).parent
                        base_output_dir = Path(args.transcription_output_dir) / adir / rel_path
                    else:
                        base_output_dir = Path(args.transcription_output_dir)
                        rel_path = None
                    
                    ext = ".txt" if args.no_srt else ".srt"
                    start_file = base_output_dir / "start_transcription" / f"{file_path.stem}_start{ext}"
                    end_file = base_output_dir / "end_transcription" / f"{file_path.stem}_end{ext}"
                    
                    if start_file.exists() and end_file.exists():
                        if not args.no_move_to_done_when_processed and adir:
                            move_to_done(file_path, args.media_base_dir, adir, rel_path)
                        
                        if not disable_pbar:
                            pbar.update(1)
                        processed_count += 1
                        continue

                total_duration = librosa.get_duration(path=file_path)
            except Exception as e:
                print(f"❌ Impossible de lire la durée de {file_path}: {e}", file=sys.stderr)
                continue

            # 1. Transcription du début
            start_content = transcribe_segment(
                file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config,
                offset=0, duration=args.duration, no_srt=args.no_srt
            )
            
            # 2. Transcription de la fin
            end_offset = max(0, total_duration - args.duration)
            end_content = transcribe_segment(
                file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config,
                offset=end_offset, duration=args.duration, no_srt=args.no_srt
            )
            
            if start_content or end_content:
                if args.stdout:
                    if start_content:
                        print(f"--- START ({file_path.name}) ---")
                        print(start_content)
                    if end_content:
                        print(f"--- END ({file_path.name}) ---")
                        print(end_content)
                else:
                    if adir:
                        audio_path = Path(args.media_base_dir) / "audio" / adir
                        rel_path = file_path.relative_to(audio_path).parent
                        base_output_dir = Path(args.transcription_output_dir) / adir / rel_path
                    else:
                        base_output_dir = Path(args.transcription_output_dir)
                    
                    ext = ".txt" if args.no_srt else ".srt"
                    
                    # Sauvegarde début
                    if start_content:
                        start_dir = base_output_dir / "start_transcription"
                        start_dir.mkdir(parents=True, exist_ok=True)
                        with open(start_dir / f"{file_path.stem}_start{ext}", 'w', encoding='utf-8') as f:
                            f.write(start_content)
                        
                    # Sauvegarde fin
                    if end_content:
                        end_dir = base_output_dir / "end_transcription"
                        end_dir.mkdir(parents=True, exist_ok=True)
                        with open(end_dir / f"{file_path.stem}_end{ext}", 'w', encoding='utf-8') as f:
                            f.write(end_content)
                    
                    if not args.no_move_to_done_when_processed and adir:
                        move_to_done(file_path, args.media_base_dir, adir, rel_path)
            else:
                if not args.stdout:
                    tqdm.write(f"ℹ️ Aucun texte détecté pour {file_path.name}", file=sys.stderr)
            
            if not disable_pbar:
                pbar.set_postfix_str(f"Fichier: {file_path.name[:20]}")
                pbar.update(1)
            
            processed_count += 1

if __name__ == "__main__":
    main()
