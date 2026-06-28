#!/usr/bin/env python3
import os
import re
import requests
import sys
import base64
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

# For transcription
import mlx.core as mx
import mlx.nn as nn
import sentencepiece
import rustymimi
import librosa
import numpy as np
from tqdm import tqdm
from huggingface_hub import hf_hub_download
from moshi_mlx import models, utils

# --- Configuration ---
# Navigate up 3 levels from 1.IAChronicleDetector/1.DataCreation/6.ScrapeAndTranscribe
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "@assets"
MEDIA_DIR = ASSETS_DIR / "0.media" / "audio"
# Output directory as requested by the user
OUTPUT_BASE_DIR = ASSETS_DIR / "1.modelOutputs" / "0.transcriptions" / "2.transcriptions_kyutai_stt_2.6b_fr"

DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

# Mapping between radio parameter and directory names
RADIO_MAP = {
    "france-inter": "4.franceinter-matin",
    "rtl": "5.rtl-matin",
    "france-info": "2.franceinfo-matin",
    "france-culture": "3.franceculture-matin",
}

# --- Utilities ---

def format_timestamp(seconds, offset_seconds=0):
    td = timedelta(seconds=float(seconds + offset_seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

# --- Scraping Logic (Adapted and simplified from existing scripts) ---

def download_file(url, dest_path, headers=None):
    if os.path.exists(dest_path):
        return True
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        if url.startswith('//'): url = 'https:' + url
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"      ❌ Error downloading {url}: {e}")
        return False

def get_audio_url_from_page(page_url, headers=None):
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        response = requests.get(page_url, timeout=10, headers=headers)
        if response.status_code != 200: return None
        # Support both mp3 and m4a
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.(mp3|m4a)", response.text)
        return match.group(0) if match else None
    except:
        return None

def scrape_radiofrance(brand, radio_id, label_time, target_date):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'}
    radio_dir_name = RADIO_MAP.get(brand)
    if not radio_dir_name: return []
    
    radio_dir = MEDIA_DIR / radio_dir_name / target_date
    chroniques_dir = radio_dir / "chroniques"
    chroniques_dir.mkdir(parents=True, exist_ok=True)
    
    clean_brand = brand.replace('-', '')
    grid_url = f"https://www.radiofrance.fr/{clean_brand}/grille-programmes?date={target_date}"
    print(f"   [*] Fetching grid: {grid_url}")
    try:
        resp = requests.get(grid_url, timeout=10, headers=headers)
        if resp.status_code != 200: 
            print(f"      ⚠️ Grid unavailable for {brand}")
            return []
        content = resp.text
        
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"
        
        # Try to find the show ID for the given time
        match = re.search(rf'label[:=]"{label_time}"[^>]*id[:=]"([a-f0-9-]{{36}})"', content)
        if not match:
            match = re.search(rf'label[:=]"{label_time}"[^>]*data-element-id[:=]"([a-f0-9-]{{36}})"', content)
        
        if not match:
            print(f"      ⚠️ Could not find show at {label_time} for {brand}")
            return []
            
        show_id = match.group(1)
        print(f"   [*] Show ID found: {show_id}")
        
        # API call to get chronicles
        payload_raw = [{"brand": 1, "parentStep": 2}, clean_brand, show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"
        
        api_resp = requests.get(api_url, headers=headers, timeout=10)
        downloaded_files = []
        if api_resp.status_code == 200:
            result_data = api_resp.json()
            result_str = str(result_data.get("result", ""))
            
            # Extract podcast links
            podcast_links = list(set(re.findall(rf'/{clean_brand}/podcasts/[^"\s\\]+', result_str)))
            print(f"   [*] Found {len(podcast_links)} potential chronicles")
            
            for link in sorted(podcast_links):
                parts = link.split('/')
                if len(parts) > 3:
                    show_name = parts[3]
                    audio_url = get_audio_url_from_page(link, headers=headers)
                    if audio_url:
                        ext = "m4a" if ".m4a" in audio_url.lower() else "mp3"
                        dest_path = chroniques_dir / f"{show_name}.{ext}"
                        if download_file(audio_url, dest_path, headers=headers):
                            print(f"      ✅ Downloaded: {show_name}")
                            downloaded_files.append(dest_path)
        return downloaded_files
    except Exception as e:
        print(f"   ❌ Error scraping {brand}: {e}")
        return []

def scrape_rtl(target_date_str):
    FEEDS = [
        ("b799ffaa-ccee-4a9a-a75f-0137a5787288", "laurent-gerra"),
        ("bd84bb2f-2f24-44a5-87ec-4851ba856c6a", "l-invite-de-rtl"),
        ("01a5bd92-d6c8-4572-8092-88e4c9953cc9", "l-oeil-de-philippe-caveriviere"),
        ("aeb105e8-907f-4710-b9d9-54ba21ca6e8c", "rtl-matin"),
    ]
    NS = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}
    try:
        target_date = datetime.strptime(target_date_str, "%d-%m-%Y")
    except ValueError:
        print(f"   ❌ Invalid date format: {target_date_str}")
        return []
        
    downloaded_files = []
    radio_dir_name = RADIO_MAP["rtl"]
    
    for feed_id, feed_slug in FEEDS:
        print(f"   [*] Checking RTL feed: {feed_slug}")
        feed_url = f"https://feeds.audiomeans.fr/feed/{feed_id}.xml"
        try:
            resp = requests.get(feed_url, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall('.//item')
            for item in items:
                pub_date_str = item.find('pubDate').text
                try:
                    # e.g. Mon, 20 Apr 2026 07:00:00 +0200
                    dt = datetime.strptime(pub_date_str[:16], "%a, %d %b %Y")
                except: continue
                
                if dt.date() == target_date.date():
                    enclosure = item.find('enclosure')
                    if enclosure is None: continue
                    audio_url = enclosure.get('url')
                    
                    title = item.find('title').text
                    # Skip integrale if in general feed
                    if feed_slug == "rtl-matin" and ("INTÉGRALE" in title.upper() or "RTL MATIN DU" in title.upper()):
                        continue
                    
                    dest_dir = MEDIA_DIR / radio_dir_name / target_date_str / "chroniques"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    
                    clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                    dest_path = dest_dir / f"{clean_title}.mp3"
                    
                    if download_file(audio_url, dest_path):
                        print(f"      ✅ Downloaded: {clean_title}")
                        downloaded_files.append(dest_path)
        except Exception as e:
            print(f"   ❌ Error scraping RTL feed {feed_slug}: {e}")
            
    return downloaded_files

# --- Transcription Logic (Adapted from batch_transcribe_starts.py) ---

def transcribe_segment(file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, offset=0, duration=20):
    try:
        # Reset caches for clean state
        if hasattr(audio_tokenizer, "reset"): audio_tokenizer.reset()
        if hasattr(model, "transformer_cache"):
            for c in model.transformer_cache: c.reset()
        if hasattr(model, "depformer_cache"):
            for c in model.depformer_cache: c.reset()
        
        # Load audio segment
        audio, _ = librosa.load(str(file_path), sr=24000, offset=offset, duration=duration)
        
        # Apply padding as per STT config
        if stt_config:
            pad_left = int(stt_config.get("audio_silence_prefix_seconds", 0.0) * 24000)
            pad_right = int((stt_config.get("audio_delay_seconds", 0.0) + 1.0) * 24000)
            audio = np.pad(audio, (pad_left, pad_right), mode="constant")
            
        steps = len(audio) // 1920
        gen = models.LmGen(
            model=model,
            max_steps=steps + 10,
            text_sampler=utils.Sampler(temp=0.0), # Greedy
            audio_sampler=utils.Sampler(temp=0.0),
            check=False,
        )
        
        all_tokens = []
        other_codebooks = lm_config.other_codebooks
        
        for idx in range(steps):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            pcm_input = pcm_chunk[None, None, :]
            
            # Encode with Mimi
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :other_codebooks]
            
            # Predict text token
            text_token = gen.step(other_audio_tokens_mx[0])
            text_token_id = text_token[0].item()
            mx.eval(gen.gen_sequence)
            
            delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
            timestamp = (idx * 0.08) - delay
            if timestamp < 0: timestamp = 0
            
            all_tokens.append((timestamp, text_token_id))

        if not all_tokens: return ""

        srt_entries = []
        current_text = []
        start_time = None
        
        for timestamp, token_id in all_tokens:
            if token_id in (0, 3): continue
            char = text_tokenizer.id_to_piece(token_id)
            char = char.replace(" ", " ").replace("▁", " ")
            if char:
                if start_time is None and char.strip():
                    start_time = timestamp
                if start_time is not None:
                    current_text.append(char)
                if len(current_text) > 15 or any(p in char for p in ".!?"):
                    end_time = timestamp + 0.08
                    text_content = "".join(current_text).strip()
                    if text_content:
                        srt_entries.append((start_time, end_time, text_content))
                    current_text = []
                    start_time = None
        
        if current_text and start_time is not None:
            srt_entries.append((start_time, all_tokens[-1][0] + 0.08, "".join(current_text).strip()))

        srt_content = ""
        for i, (start, end, text) in enumerate(srt_entries):
            srt_content += f"{i+1}\n"
            srt_content += f"{format_timestamp(start, offset)} --> {format_timestamp(end, offset)}\n"
            srt_content += f"{text}\n\n"
        return srt_content
    except Exception as e:
        print(f"   ❌ Error transcribing {file_path.name}: {e}")
        return None

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Scrape chronicles and transcribe their first sentences using Kyutai STT.")
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"], help="Radio station slug")
    parser.add_argument("--date", type=str, help="Target date in DD-MM-YYYY format (default: today)")
    parser.add_argument("--duration", type=int, default=20, help="Duration to transcribe in seconds (default: 20)")
    parser.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID, help=f"Hugging Face model ID (default: {DEFAULT_MODEL_ID})")
    
    args = parser.parse_args()
    
    target_date = args.date if args.date else datetime.now().strftime("%d-%m-%Y")
    
    print(f"🚀 Starting process for {args.radio} on {target_date}...")
    
    # 1. Scraping
    files = []
    if args.radio == "france-inter":
        files = scrape_radiofrance("france-inter", "franceinter", "07h00", target_date)
    elif args.radio == "france-info":
        files = scrape_radiofrance("france-info", "franceinfo", "06h00", target_date)
    elif args.radio == "france-culture":
        files = scrape_radiofrance("france-culture", "franceculture", "07h00", target_date)
    elif args.radio == "rtl":
        files = scrape_rtl(target_date)
        
    if not files:
        print("ℹ️ No chronicles found or downloaded.")
        return

    print(f"✅ Found {len(files)} chronicles. Initializing STT model...")
    
    # 2. Model Initialization
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
        
        if weights_path.endswith(".q4.safetensors"):
            nn.quantize(model, bits=4, group_size=32)
        elif weights_path.endswith(".q8.safetensors"):
            nn.quantize(model, bits=8, group_size=64)
            
        model.load_weights(weights_path)
        
        tokenizer_path = hf_hub_download(args.model_id, config_dict["tokenizer_name"])
        text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
        
        mimi_path = hf_hub_download(args.model_id, config_dict["mimi_name"])
        audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
        
        model.warmup()
    except Exception as e:
        print(f"❌ Failed to initialize model: {e}")
        return

    # 3. Transcription
    chroniques_out_dir = OUTPUT_BASE_DIR / RADIO_MAP[args.radio] / target_date / "chroniques"
    start_dir = chroniques_out_dir / "start_transcription"
    end_dir = chroniques_out_dir / "end_transcription"
    
    start_dir.mkdir(parents=True, exist_ok=True)
    end_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📝 Transcribing and saving results to: {chroniques_out_dir}")
    
    results_count = 0
    for f_path in tqdm(files, desc="Transcribing", unit="file"):
        try:
            total_duration = librosa.get_duration(path=str(f_path))
        except Exception as e:
            print(f"   ❌ Could not get duration for {f_path.name}: {e}")
            continue

        # Transcribe Start
        start_transcription = transcribe_segment(
            f_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, 
            offset=0, duration=args.duration
        )
        if start_transcription:
            with open(start_dir / f"{f_path.stem}_start.srt", "w", encoding="utf-8") as out:
                out.write(start_transcription)
        
        # Transcribe End
        end_offset = max(0, total_duration - args.duration)
        end_transcription = transcribe_segment(
            f_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, 
            offset=end_offset, duration=args.duration
        )
        if end_transcription:
            with open(end_dir / f"{f_path.stem}_end.srt", "w", encoding="utf-8") as out:
                out.write(end_transcription)
        
        if start_transcription or end_transcription:
            results_count += 1

    print(f"✨ Successfully processed {results_count}/{len(files)} chronicles.")
    print(f"📂 Output saved in: {chroniques_out_dir}")

if __name__ == "__main__":
    main()
