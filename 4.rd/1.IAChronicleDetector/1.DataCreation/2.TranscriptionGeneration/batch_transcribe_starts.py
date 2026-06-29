#!/usr/bin/env python3
"""
Script pour transcrire les 10 premières secondes de chaque chronique dans un dossier
et regrouper les résultats dans un seul fichier texte.
"""

import os
import sys
import json
import argparse
from pathlib import Path
import mlx.core as mx
import mlx.nn as nn
import sentencepiece
import rustymimi
import librosa
import numpy as np
from tqdm import tqdm
from huggingface_hub import hf_hub_download
from moshi_mlx import models, utils

# Configuration par défaut
DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Transcrit les 10 premières secondes des chroniques d'un dossier dans un fichier unique."
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Dossier contenant les chroniques à traiter"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Durée à transcrire au début (défaut: 10.0s)"
    )
    parser.add_argument(
        "--hf-repo",
        type=str,
        default=DEFAULT_MODEL_ID,
        help=f"Repo Hugging Face du modèle (défaut: {DEFAULT_MODEL_ID})"
    )
    return parser.parse_args()

def transcribe_segment(file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, duration=10):
    try:
        # Reset des caches
        if hasattr(audio_tokenizer, "reset"): audio_tokenizer.reset()
        if hasattr(model, "transformer_cache"):
            for c in model.transformer_cache: c.reset()
        if hasattr(model, "depformer_cache"):
            for c in model.depformer_cache: c.reset()

        # Charger l'audio
        audio, _ = librosa.load(str(file_path), sr=24000, offset=0, duration=duration)
        
        # Padding
        if stt_config:
            pad_left = int(stt_config.get("audio_silence_prefix_seconds", 0.0) * 24000)
            pad_right = int((stt_config.get("audio_delay_seconds", 0.0) + 1.0) * 24000)
            audio = np.pad(audio, (pad_left, pad_right), mode="constant")
        
        steps = len(audio) // 1920
        gen = models.LmGen(
            model=model,
            max_steps=steps + 10,
            text_sampler=utils.Sampler(temp=0.0),
            audio_sampler=utils.Sampler(temp=0.0),
            check=False,
        )
        
        all_text = []
        other_codebooks = lm_config.other_codebooks
        
        for idx in range(steps):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            pcm_input = pcm_chunk[None, None, :]
            
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
            
            text_token = gen.step(other_audio_tokens_mx[0])
            text_token_id = text_token[0].item()
            mx.eval(gen.gen_sequence)
            
            if text_token_id not in (0, 3):
                char = text_tokenizer.id_to_piece(text_token_id)
                all_text.append(char)

        return "".join(all_text).replace(" ", " ").replace("▁", " ").strip()
            
    except Exception as e:
        print(f"\nError transcribing {file_path.name}: {e}", file=sys.stderr)
        return None

def main():
    args = parse_arguments()
    input_path = Path(args.input_dir)
    
    if not input_path.is_dir():
        print(f"Error: {args.input_dir} is not a directory.")
        sys.exit(1)

    output_file = input_path.parent / f"{input_path.name}_transcriptions.txt"
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".m4b"}
    
    files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS])
    
    if not files:
        print("No audio files found in the directory.")
        return

    print(f"Loading model {args.hf_repo}...")
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
        print(f"Initialization error: {e}")
        return

    print(f"Transcribing {len(files)} files to {output_file.name}...")
    
    with open(output_file, "w", encoding="utf-8") as out:
        for f in tqdm(files, unit="file"):
            transcription = transcribe_segment(
                f, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, duration=args.duration
            )
            if transcription:
                out.write(f"{transcription}\n")
            else:
                out.write("[Transcription failed]\n")
            out.flush() # Ensure writing in case of crash

    print(f"\nDone! Results saved in: {output_file}")

if __name__ == "__main__":
    main()
