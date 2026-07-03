#!/usr/bin/env python3
import subprocess
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

# --- Utilities ---

def get_audio_duration(file_path):
    """Get duration of an audio file using ffprobe, fallback to librosa."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return librosa.get_duration(path=str(file_path))

# Navigate up 3 levels from 1.IAChronicleDetector/1.DataCreation/6.ScrapeAndTranscribe
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "@assets"
MEDIA_DIR = ASSETS_DIR / "0.media" / "audio"
# Output directory
OUTPUT_BASE_DIR = ASSETS_DIR / "1.modelOutputs" / "0.transcriptions" / "2.transcriptions_kyutai_stt_2.6b_fr"

DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr-mlx"

# Mapping between radio parameter and directory names
RADIO_MAP = {
    "france-inter": "4.franceinter-matin",
    "rtl": "5.rtl-matin",
    "france-info": "2.franceinfo-matin",
    "france-culture": "3.franceculture-matin",
}

# --- Scraping Logic (Radio France) ---

def download_file(url, dest_path, headers=None, dry_run=False):
    if url.startswith('//'): url = 'https:' + url
    
    if dry_run:
        print(f"      [DRY-RUN] Would download: {url}")
        print(f"                To: {dest_path}")
        return True
    
    if os.path.exists(dest_path):
        print(f"      ✅ File already exists: {os.path.basename(dest_path)}")
        return True

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"      📥 Downloading from: {url}")
    
    try:
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
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.(mp3|m4a)", response.text)
        return match.group(0) if match else None
    except:
        return None

def scrape_radiofrance_chronicles(brand, target_date, label_time="07h00", dry_run=False):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'}
    radio_dir_name = RADIO_MAP.get(brand)
    if not radio_dir_name: return []
    
    chroniques_dir = MEDIA_DIR / radio_dir_name / target_date / "chroniques"
    chroniques_dir.mkdir(parents=True, exist_ok=True)
    
    clean_brand = brand.replace('-', '')
    grid_url = f"https://www.radiofrance.fr/{clean_brand}/grille-programmes?date={target_date}"
    print(f"   [*] Fetching grid: {grid_url}")
    
    try:
        resp = requests.get(grid_url, timeout=10, headers=headers)
        if resp.status_code != 200: return []
        content = resp.text
        
        # Build hash pour l'API
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"

        # On cherche le bloc correspondant au label (ex: 07h00)
        match = re.search(rf'label:"{label_time}"[^}}]*id:"([a-f0-9-]{{36}})"', content)
        if not match:
            match = re.search(rf'label="{label_time}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
        
        if not match:
            print(f"      ⚠️ Segment not found for {label_time}")
            return []
            
        show_id = match.group(1)
        
        # Extraction du lien principal
        link_match = re.search(rf'label[:=]"{label_time}".*?href[:=]"([^"]+)"', content, re.DOTALL)
        if not link_match:
            link_match = re.search(rf'label:"{label_time}".*?href:"([^"]+)"', content, re.DOTALL)
        main_link = link_match.group(1) if link_match else None

        # Appel API Chroniques
        payload_raw = [{"brand": 1, "parentStep": 2}, clean_brand, show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

        downloaded_files = []
        api_resp = requests.get(api_url, headers=headers, timeout=10)
        if api_resp.status_code == 200:
            result_data = api_resp.json()
            result_str = str(result_data.get("result", ""))
            
            # Extract podcast links
            podcast_links = list(set(re.findall(rf'/(?:{clean_brand}|{brand})/podcasts/[^"\s\\]+', result_str)))
            
            for link in sorted(podcast_links):
                if main_link and (link == main_link or main_link in link): continue
                
                parts = link.split('/')
                if len(parts) > 3:
                    show_name = parts[3]
                    audio_url = get_audio_url_from_page(link, headers=headers)
                    if audio_url:
                        ext = "m4a" if ".m4a" in audio_url.lower() else "mp3"
                        dest_path = chroniques_dir / f"{show_name}.{ext}"
                        if download_file(audio_url, dest_path, headers=headers, dry_run=dry_run):
                            downloaded_files.append(dest_path)
        return downloaded_files
    except Exception as e:
        print(f"   ❌ Error scraping {brand}: {e}")
        return []

def scrape_rtl_chronicles(target_date_str, dry_run=False):
    FEEDS = [
        ("b799ffaa-ccee-4a9a-a75f-0137a5787288", "laurent-gerra"),
        ("bd84bb2f-2f24-44a5-87ec-4851ba856c6a", "l-invite-de-rtl"),
        ("01a5bd92-d6c8-4572-8092-88e4c9953cc9", "l-oeil-de-philippe-caveriviere"),
        ("aeb105e8-907f-4710-b9d9-54ba21ca6e8c", "rtl-matin"),
    ]
    try:
        target_date = datetime.strptime(target_date_str, "%d-%m-%Y")
    except: return []
        
    downloaded_files = []
    radio_dir_name = RADIO_MAP["rtl"]
    
    for feed_id, feed_slug in FEEDS:
        feed_url = f"https://feeds.audiomeans.fr/feed/{feed_id}.xml"
        try:
            resp = requests.get(feed_url, timeout=20)
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                pub_date_str = item.find('pubDate').text
                try:
                    dt = datetime.strptime(pub_date_str[:16], "%a, %d %b %Y")
                except: continue
                
                if dt.date() == target_date.date():
                    title = item.find('title').text
                    if "INTÉGRALE" in title.upper() or "RTL MATIN DU" in title.upper():
                        continue
                        
                    enclosure = item.find('enclosure')
                    if enclosure is None: continue
                    audio_url = enclosure.get('url')
                    
                    dest_dir = MEDIA_DIR / radio_dir_name / target_date_str / "chroniques"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                    dest_path = dest_dir / f"{clean_title}.mp3"
                    
                    if download_file(audio_url, dest_path, dry_run=dry_run):
                        downloaded_files.append(dest_path)
        except: pass
    return downloaded_files

# --- Transcription Logic ---

import gc
mx.metal.set_cache_limit(4 * 1024 * 1024 * 1024)

def transcribe_segment(file_path, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=0, duration=None):
    temp_wav = None
    try:
        audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
        model.transformer_cache = model.transformer.make_rot_cache()
        if hasattr(model, "depformer_cache") and model.depformer.slices:
            model.depformer_cache = model.depformer.slices[0].transformer.make_cache()
        mx.eval(model.transformer_cache)

        temp_wav = file_path.with_suffix(f".{os.getpid()}.temp.wav")
        subprocess.run(["ffmpeg", "-i", str(file_path), "-ar", "24000", "-ac", "1", "-y", str(temp_wav), "-loglevel", "error"], check=True)

        total_duration = get_audio_duration(temp_wav)
        if duration is not None: total_duration = min(total_duration, duration)

        audio, _ = librosa.load(str(temp_wav), sr=24000, offset=offset, duration=total_duration)
        
        if stt_config and offset == 0:
            pad_left = int(stt_config.get("audio_silence_prefix_seconds", 0.0) * 24000)
            pad_right = int((stt_config.get("audio_delay_seconds", 0.0) + 1.0) * 24000)
            audio = np.pad(audio, (pad_left, pad_right), mode="constant")
        
        steps = len(audio) // 1920
        gen = models.LmGen(model=model, max_steps=steps + 10, text_sampler=utils.Sampler(temp=0.0), audio_sampler=utils.Sampler(temp=0.0), check=False)
        
        chunk_tokens = []
        for idx in range(steps):
            pcm_chunk = audio[idx * 1920:(idx + 1) * 1920]
            pcm_input = pcm_chunk[None, None, :]
            other_audio_tokens = audio_tokenizer.encode_step(pcm_input)
            other_audio_tokens_mx = mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :lm_config.other_codebooks]
            text_token = gen.step(other_audio_tokens_mx[0])
            mx.eval(gen.gen_sequence)
            
            delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
            timestamp = (idx * 0.08) - delay
            chunk_tokens.append((max(0, timestamp), text_token[0].item()))
        
        all_text = []
        for _, token_id in chunk_tokens:
            if token_id in (0, 3): continue
            char = text_tokenizer.id_to_piece(token_id).replace(" ", " ").replace("▁", " ")
            if char: all_text.append(char)
            
        return "".join(all_text).strip()
    except Exception as e:
        print(f"   ❌ Error transcribing {file_path.name}: {e}")
        return None
    finally:
        if temp_wav and temp_wav.exists(): temp_wav.unlink()

def main():
    parser = argparse.ArgumentParser(description="Scrape and transcribe ONLY chronicles.")
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"], help="Radio station slug")
    parser.add_argument("--date", type=str, help="Target date in DD-MM-YYYY format (default: today)")
    parser.add_argument("--duration", type=int, default=30, help="Duration to transcribe in seconds (default: 30)")
    parser.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID, help=f"Hugging Face model ID")
    parser.add_argument("--dry-run", action="store_true", help="Show URLs without downloading or transcribing")
    
    args = parser.parse_args()
    target_date = args.date if args.date else datetime.now().strftime("%d-%m-%Y")
    
    print(f"🚀 Scraping chronicles for {args.radio} on {target_date}...")
    
    files = []
    if args.radio == "rtl":
        files = scrape_rtl_chronicles(target_date, dry_run=args.dry_run)
    else:
        label = "06h00" if args.radio == "france-info" else "07h00"
        files = scrape_radiofrance_chronicles(args.radio, target_date, label, dry_run=args.dry_run)
        
    if args.dry_run:
        print(f"\n✅ Dry-run completed. Found {len(files)} chronicles.")
        return

    if not files:
        radio_dir_name = RADIO_MAP.get(args.radio)
        chroniques_local_dir = MEDIA_DIR / radio_dir_name / target_date / "chroniques"
        if chroniques_local_dir.exists():
            files = [f for f in chroniques_local_dir.glob("*") if f.suffix.lower() in ['.mp3', '.m4a']]

    if not files:
        print("ℹ️ No chronicles found.")
        return

    print(f"✅ Found {len(files)} chronicles. Initializing model...")
    
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
    except Exception as e:
        print(f"❌ Model init failed: {e}")
        return

    base_out_dir = OUTPUT_BASE_DIR / RADIO_MAP[args.radio] / target_date
    chroniques_out_dir = base_out_dir / "chroniques"
    start_dir = chroniques_out_dir / "start_transcription"
    
    start_dir.mkdir(parents=True, exist_ok=True)
    
    for i, f_path in enumerate(files):
        print(f"   [{i+1}/{len(files)}] Transcribing {f_path.name}...")
        txt = transcribe_segment(f_path, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=0, duration=args.duration)
        if txt:
            out_file = start_dir / f"{f_path.stem}_start.txt"
            with open(out_file, "w", encoding="utf-8") as out:
                out.write(txt)
            print(f"      ✅ Saved: {out_file.name}")

    print(f"✨ Done. Outputs in: {start_dir}")

if __name__ == "__main__":
    main()
