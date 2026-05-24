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
DEFAULT_MEDIA_BASE_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/0.media"
DEFAULT_TRANSCRIPTION_OUTPUT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr"
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

def parse_arguments():
    """Parse les arguments de ligne de commande"""
    parser = argparse.ArgumentParser(
        description="Transcrit des fichiers audio avec Kyutai STT (MLX) et les déplace vers audio-done",
        formatter_class=argparse.RawDescriptionHelpFormatter
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

def transcribe_audio_mlx(file_path, output_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config):
    """
    Transcrit un fichier audio en utilisant MLX et rustymimi
    """
    import mlx.core as mx
    import numpy as np
    import librosa
    from moshi_mlx import utils
    
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
        from tqdm import tqdm
        file_name = os.path.basename(file_path)
        for idx in tqdm(range(steps), desc=f"   └─ {file_name[:30]}", unit="step", leave=False):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            # rustymimi attend (batch, channels, samples) -> (1, 1, 1920)
            pcm_input = pcm_chunk[None, None, :]
            
            # Encodage Mimi
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            # other_audio_tokens shape via rustymimi is (batch, samples, codebooks)
            # Moshi LmGen attend (codebooks, steps)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
            
            # Step du modèle
            text_token = gen.step(other_audio_tokens_mx[0])
            text_token_id = text_token[0].item()
            
            # On stocke le token avec son timestamp (ajusté du délai audio)
            # Le délai audio_delay_seconds est souvent de 0.5s
            delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
            timestamp = (idx * 0.08) - delay
            if timestamp < 0: timestamp = 0
            
            all_tokens.append((timestamp, text_token_id))

        # Reconstruction du texte et SRT
        srt_entries = []
        current_text = []
        start_time = None
        
        for timestamp, token_id in all_tokens:
            # 0 et 3 sont souvent des tokens de padding/silence
            if token_id in (0, 3):
                continue
                
            char = text_tokenizer.id_to_piece(token_id)
            char = char.replace(" ", " ") # Sentencepiece space
            char = char.replace("▁", "")
            
            if char.strip():
                if start_time is None:
                    start_time = timestamp
                current_text.append(char)
                
                # Découpage arbitraire pour SRT (tous les 10 tokens ou sur ponctuation)
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

        # Ecriture SRT
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, (start, end, text) in enumerate(srt_entries):
                f.write(f"{i+1}\n")
                f.write(f"{format_timestamp(start)} --> {format_timestamp(end)}\n")
                f.write(f"{text}\n\n")
        
        return True
            
    except Exception as e:
        print(f"Exception lors de la transcription MLX: {e}")
        import traceback
        traceback.print_exc()
        return False

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
    
    # Récupération des dossiers audio
    audio_base = Path(args.media_base_dir) / "audio"
    if not audio_base.exists():
        print(f"❌ Dossier source introuvable: {audio_base}")
        return
        
    audio_dirs = sorted([d.name for d in audio_base.iterdir() if d.is_dir() and not d.name.startswith('.')])
    
    print(f"🖥️  MLX Device: GPU (Metal)")
    print(f"📥 Chargement du modèle depuis {args.hf_repo}...")
    
    try:
        config_path = hf_hub_download(args.hf_repo, "config.json")
        with open(config_path, "r") as f:
            config_dict = json.load(f)
            
        stt_config = config_dict.get("stt_config")
        lm_config = models.LmConfig.from_config_dict(config_dict)
        model = models.Lm(lm_config)
        model.set_dtype(mx.bfloat16)
        
        # Chargement des poids
        weights_path = hf_hub_download(args.hf_repo, config_dict.get("moshi_name", "model.safetensors"))
        # Gestion de la quantification si nécessaire (ici on assume bf16 par défaut pour stt-1b)
        if weights_path.endswith(".q4.safetensors"):
            nn.quantize(model, bits=4, group_size=32)
        elif weights_path.endswith(".q8.safetensors"):
            nn.quantize(model, bits=8, group_size=64)
            
        model.load_weights(weights_path)
        
        # Tokenizers
        tokenizer_path = hf_hub_download(args.hf_repo, config_dict["tokenizer_name"])
        text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
        
        mimi_path = hf_hub_download(args.hf_repo, config_dict["mimi_name"])
        audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
        
        model.warmup()
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        import traceback
        traceback.print_exc()
        return

    # Scan des fichiers
    all_files = []
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".m4b"}
    
    for adir in audio_dirs:
        path = audio_base / adir
        files = [f for f in path.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS]
        for f in files:
            all_files.append((f, adir))
            
    if not all_files:
        print("ℹ️ Aucun fichier à traiter.")
        return

    # Limite si spécifiée
    if args.max_files_to_process:
        all_files = all_files[:args.max_files_to_process]
        print(f"⚠️ Limité à {args.max_files_to_process} fichiers par l'option --max-files-to-process")

    print(f"🚀 Traitement de {len(all_files)} fichiers...")
    
    with tqdm(total=len(all_files), unit="file", desc="Transcription MLX") as pbar:
        for file_path, adir in all_files:
            audio_path = audio_base / adir
            rel_path = file_path.relative_to(audio_path).parent
            output_dir = Path(args.transcription_output_dir) / adir / rel_path
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = output_dir / f"{file_path.stem}_transcription.srt"
            pbar.set_postfix_str(f"Fichier: {file_path.name[:20]}")
            
            success = transcribe_audio_mlx(
                file_path, 
                output_file, 
                model, 
                audio_tokenizer, 
                text_tokenizer, 
                lm_config, 
                stt_config
            )
            
            if success:
                if not args.no_move_to_done_when_processed:
                    move_to_done(file_path, args.media_base_dir, adir, rel_path)
            else:
                tqdm.write(f"❌ Échec pour {file_path.name}")
            
            pbar.update(1)

if __name__ == "__main__":
    main()
