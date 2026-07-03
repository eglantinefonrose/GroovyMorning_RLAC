#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from huggingface_hub import hf_hub_download

# For transcription
import mlx.core as mx
import mlx.nn as nn
import sentencepiece
from moshi_mlx import models

# Import the processing logic from the original script
import scrape_and_transcribe as st

def main():
    parser = argparse.ArgumentParser(description="Batch scrape and transcribe for a range of dates.")
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"], help="Radio station slug")
    parser.add_argument("start_date", type=str, help="Start date in DD-MM-YYYY format")
    parser.add_argument("end_date", type=str, help="End date in DD-MM-YYYY format")
    parser.add_argument("--duration", type=int, default=30, help="Duration to transcribe for segments in seconds (default: 30)")
    parser.add_argument("--model-id", type=str, default=st.DEFAULT_MODEL_ID, help=f"Hugging Face model ID")
    parser.add_argument("--dry-run", action="store_true", help="Show URLs without downloading or transcribing")
    
    args = parser.parse_args()
    
    try:
        start_dt = datetime.strptime(args.start_date, "%d-%m-%Y")
        end_dt = datetime.strptime(args.end_date, "%d-%m-%Y")
    except ValueError as e:
        print(f"❌ Invalid date format: {e}")
        return

    if start_dt > end_dt:
        print("❌ Start date must be before or equal to end date.")
        return

    print(f"🚀 Batch process for {args.radio} from {args.start_date} to {args.end_date}...")
    
    model = None
    mimi_path = None
    text_tokenizer = None
    lm_config = None
    stt_config = None

    if not args.dry_run:
        print(f"   Initializing STT model once for the entire batch...")
        try:
            config_path = hf_hub_download(args.model_id, "config.json")
            with open(config_path, "r") as f:
                config_dict = json.load(f)
            stt_config = config_dict.get("stt_config")
            lm_config = models.LmConfig.from_config_dict(config_dict)
            model = models.Lm(lm_config)
            model.set_dtype(mx.bfloat16)
            
            weights_name = config_dict.get("moshi_name", "model.safetensors")
            weights_path = hf_hub_download(args.model_id, weights_name)
            if weights_path.endswith(".q4.safetensors"): nn.quantize(model, bits=4, group_size=32)
            elif weights_path.endswith(".q8.safetensors"): nn.quantize(model, bits=8, group_size=64)
            model.load_weights(weights_path)
            
            text_tokenizer = sentencepiece.SentencePieceProcessor(hf_hub_download(args.model_id, config_dict["tokenizer_name"]))
            mimi_path = hf_hub_download(args.model_id, config_dict["mimi_name"])
            model.warmup()
            print("   ✅ Model initialized.")
        except Exception as e:
            print(f"❌ Model init failed: {e}")
            return

    curr_dt = start_dt
    while curr_dt <= end_dt:
        # France Inter constraint: only Mon, Tue, Wed, Thu
        # weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        is_france_inter = args.radio == "france-inter"
        if is_france_inter and curr_dt.weekday() > 3:
            print(f"\n[INFO] Skipping {curr_dt.strftime('%d-%m-%Y')} (France Inter - Week-end/Friday policy)")
        else:
            target_date_str = curr_dt.strftime("%d-%m-%Y")
            st.process_single_date(
                args.radio, target_date_str, args.duration, 
                model, mimi_path, text_tokenizer, lm_config, stt_config,
                dry_run=args.dry_run
            )
            
        curr_dt += timedelta(days=1)

    print(f"\n✨ Batch process completed.")

if __name__ == "__main__":
    main()
