#!/usr/bin/env python3
"""
Transcription d'un fichier audio unique avec Kyutai STT (MLX Version)
Optimisé pour Apple Silicon (M1/M2/M3)
Supporte les fichiers longs par découpage en segments (chunking)
Usage: python kyutai_transcribe.py <audio_file> [options]
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import timedelta

# Configuration par défaut
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit un fichier audio unique avec Kyutai STT (MLX)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "input",
        type=str,
        help="Chemin vers le fichier audio à traiter"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Chemin du fichier de sortie (par défaut: même nom que l'entrée avec .srt)"
    )
    
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Afficher la transcription sur stdout au lieu de l'écrire dans un fichier"
    )
    
    parser.add_argument(
        "--txt",
        action="store_true",
        help="Générer uniquement du texte brut sans formatage SRT"
    )
    
    parser.add_argument(
        "--hf-repo",
        type=str,
        default=DEFAULT_MODEL_ID,
        help=f"Repo Hugging Face du modèle MLX (défaut: {DEFAULT_MODEL_ID})"
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

def transcribe_audio_mlx(file_path, model, mimi_path, text_tokenizer, lm_config, stt_config, no_srt=False):
    """
    Transcrit un fichier audio en utilisant MLX et rustymimi.
    Gère les fichiers longs par segmentation.
    """
    import mlx.core as mx
    import librosa
    import rustymimi
    from moshi_mlx import utils
    from moshi_mlx.models import LmGen
    from tqdm import tqdm
    
    try:
        # Charger l'audio et rééchantillonner à 24kHz
        audio, _ = librosa.load(file_path, sr=24000)
        
        # Padding initial selon la config STT
        if stt_config:
            pad_left_sec = stt_config.get("audio_silence_prefix_seconds", 0.0)
            if pad_left_sec > 0:
                pad_left = int(pad_left_sec * 24000)
                audio = np.pad(audio, (pad_left, 0), mode="constant")
        
        steps = len(audio) // 1920
        all_tokens = []
        other_codebooks = lm_config.other_codebooks
        
        # Paramètres de chunking pour éviter de dépasser max_seq_len (4096/8192)
        chunk_size_steps = 3000 # ~4 minutes par chunk
        overlap_steps = 125    # 10 secondes d'overlap pour la continuité
        
        file_name = os.path.basename(file_path)
        pbar = tqdm(total=steps, desc=f"Transcribing {file_name[:30]}", unit="step", leave=False, file=sys.stderr)
        
        for start_step in range(0, steps, chunk_size_steps - overlap_steps):
            end_step = min(start_step + chunk_size_steps, steps)
            if end_step <= start_step: break
            
            # Recréation du tokenizer pour garantir un reset complet de l'état
            audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
            
            # Reset de l'état du LM pour chaque segment
            for c in model.transformer_cache:
                c.reset()
                
            # Initialisation du générateur pour ce segment
            gen = LmGen(
                model=model,
                max_steps=(end_step - start_step) + 10,
                text_sampler=utils.Sampler(temp=0.0),
                audio_sampler=utils.Sampler(temp=0.0),
                check=False,
            )
            
            # Détermination de la zone à conserver pour éviter les doublons dus à l'overlap
            # On prend la moitié de l'overlap comme frontière
            keep_start_rel = 0 if start_step == 0 else (overlap_steps // 2)
            keep_end_rel = (end_step - start_step) if end_step == steps else (end_step - start_step) - (overlap_steps // 2)
            
            for rel_idx in range(end_step - start_step):
                abs_idx = start_step + rel_idx
                
                pcm_chunk = audio[abs_idx * 1920:(abs_idx + 1) * 1920]
                if len(pcm_chunk) < 1920:
                    pcm_chunk = np.pad(pcm_chunk, (0, 1920 - len(pcm_chunk)))
                
                pcm_input = pcm_chunk[None, None, :]
                
                # Encodage Mimi
                other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
                other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
                
                # Step du modèle
                text_token = gen.step(other_audio_tokens_mx[0])
                text_token_id = text_token[0].item()
                
                # On ne garde que les tokens dans la zone de validité
                if keep_start_rel <= rel_idx < keep_end_rel:
                    delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
                    timestamp = (abs_idx * 0.08) - delay
                    if timestamp < 0: timestamp = 0
                    all_tokens.append((timestamp, text_token_id))
                
                pbar.update(1)
            
            # S'assurer que pbar est à jour si on a sauté des étapes à cause de keep_end_rel
            # Mais ici on boucle sur tous les steps du chunk donc update(1) est correct.
            
        pbar.close()

        # Reconstruction du texte et SRT
        srt_entries = []
        current_text = []
        start_time = None
        
        for timestamp, token_id in all_tokens:
            if token_id in (0, 3): # Tokens spéciaux / padding
                continue
                
            char = text_tokenizer.id_to_piece(token_id)
            char = char.replace(" ", " ") 
            char = char.replace("▁", " ")
            
            if char:
                if start_time is None and char.strip():
                    start_time = timestamp
                
                if start_time is not None:
                    current_text.append(char)
                
                # Découpage en segments SRT (par ponctuation ou longueur)
                if len(current_text) > 12 or any(p in char for p in ".!?"):
                    end_time = timestamp + 0.08
                    text_content = "".join(current_text).strip()
                    if text_content:
                        srt_entries.append((start_time, end_time, text_content))
                    current_text = []
                    start_time = None
        
        if current_text and start_time is not None:
            srt_entries.append((start_time, all_tokens[-1][0] + 0.08, "".join(current_text).strip()))

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
        print(f"Error during transcription: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None

def main():
    args = parse_arguments()
    
    # Importations lourdes différées
    import mlx.core as mx
    import mlx.nn as nn
    import sentencepiece
    import rustymimi
    from huggingface_hub import hf_hub_download
    from moshi_mlx import models
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.stdout:
        print(f"🖥️  MLX Device: GPU (Metal)", file=sys.stderr)
        print(f"📥 Loading model from {args.hf_repo}...", file=sys.stderr)
    
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
        print(f"❌ Initialization error: {e}", file=sys.stderr)
        sys.exit(1)

    srt_content = transcribe_audio_mlx(
        input_path, 
        model, 
        mimi_path, 
        text_tokenizer, 
        lm_config, 
        stt_config,
        no_srt=args.txt
    )
    
    if srt_content:
        if args.stdout:
            print(srt_content)
        else:
            if args.output:
                output_file = Path(args.output)
            else:
                ext = ".txt" if args.txt else ".srt"
                output_file = input_path.with_suffix(ext)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            print(f"✅ Transcription saved to: {output_file}")
    else:
        print(f"❌ Transcription failed for {input_path}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
