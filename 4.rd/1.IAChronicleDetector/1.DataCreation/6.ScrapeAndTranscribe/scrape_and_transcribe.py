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
    if not radio_dir_name: return [], None
    
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
            return [], None
        content = resp.text
        
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"
        
        # Try to find the show ID and path for the given time
        show_match = re.search(rf'label[:=]"{label_time}"[^>]*id[:=]"([a-f0-9-]{{36}})"', content)
        if not show_match:
            show_match = re.search(rf'label[:=]"{label_time}"[^>]*data-element-id[:=]"([a-f0-9-]{{36}})"', content)
        
        if not show_match:
            print(f"      ⚠️ Could not find show at {label_time} for {brand}")
            return [], None
            
        show_id = show_match.group(1)
        print(f"   [*] Show ID found: {show_id}")

        # Try to find the show path for full show download
        full_show_path = None
        # Try finding path or href after label
        path_match = re.search(rf'label[:=]"{label_time}"[^}}]*"?(?:path|href)"?[:=]"([^"]+)"', content)
        if not path_match:
            # Try finding path or href before label
            path_match = re.search(rf'"?(?:path|href)"?[:=]"([^"]+)"[^}}]*label[:=]"{label_time}"', content)
        
        if path_match:
            show_path = path_match.group(1)
            print(f"   [*] Show path found: {show_path}")
            full_audio_url = get_audio_url_from_page(show_path, headers=headers)
            if full_audio_url:
                ext = "m4a" if ".m4a" in full_audio_url.lower() else "mp3"
                dest_path = radio_dir / f"full_show.{ext}"
                if download_file(full_audio_url, dest_path, headers=headers):
                    print(f"      ✅ Downloaded Full Show: {dest_path.name}")
                    full_show_path = dest_path
        
        # fallback check for existing emission file
        if not full_show_path:
            for existing in radio_dir.glob("*Emission*"):
                if existing.suffix.lower() in ['.mp3', '.m4a']:
                    print(f"   [*] Found existing emission file: {existing.name}")
                    full_show_path = existing
                    break
        
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
        return downloaded_files, full_show_path
    except Exception as e:
        print(f"   ❌ Error scraping {brand}: {e}")
        return [], None

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
        return [], None
        
    downloaded_files = []
    full_show_file = None
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
                    
                    # Handle integrale vs chronicles
                    is_integrale = ("INTÉGRALE" in title.upper() or "RTL MATIN DU" in title.upper())
                    
                    if is_integrale:
                        dest_dir = MEDIA_DIR / radio_dir_name / target_date_str
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / "full_show.mp3"
                        if download_file(audio_url, dest_path):
                            print(f"      ✅ Downloaded Full Show: {title}")
                            full_show_file = dest_path
                    else:
                        dest_dir = MEDIA_DIR / radio_dir_name / target_date_str / "chroniques"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        
                        clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                        dest_path = dest_dir / f"{clean_title}.mp3"
                        
                        if download_file(audio_url, dest_path):
                            print(f"      ✅ Downloaded: {clean_title}")
                            downloaded_files.append(dest_path)
        except Exception as e:
            print(f"   ❌ Error scraping RTL feed {feed_slug}: {e}")
            
    # fallback check for existing integrale file
    if not full_show_file:
        rtl_dir = MEDIA_DIR / RADIO_MAP["rtl"] / target_date_str
        for existing in rtl_dir.glob("*.mp3"):
            if existing.name == f"{target_date_str}.mp3" or "integrale" in existing.name.lower():
                print(f"   [*] Found existing RTL integrale: {existing.name}")
                full_show_file = existing
                break

    return downloaded_files, full_show_file

# --- Transcription Logic (Adapted from batch_transcribe_starts.py) ---

import gc

# Limit MLX cache to 4GB to prevent system saturation
mx.metal.set_cache_limit(4 * 1024 * 1024 * 1024)

def transcribe_segment(file_path, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, offset=0, duration=None):
    temp_wav = None
    try:
        # 1. Convert to temporary WAV if not already (SoundFile is much better with WAV)
        # This avoids the slow and RAM-hungry 'audioread' fallback
        print(f"   [*] Preparing audio for {file_path.name}...")
        temp_wav = file_path.with_suffix(f".{os.getpid()}.temp.wav")
        conv_cmd = [
            "ffmpeg", "-i", str(file_path),
            "-ar", "24000", "-ac", "1", # Mono 24kHz
            "-y", str(temp_wav), "-loglevel", "error"
        ]
        subprocess.run(conv_cmd, check=True)

        total_duration = get_audio_duration(temp_wav)
        if duration is not None:
            total_duration = min(total_duration, duration)

        # Process in micro-chunks of 30 seconds for maximum RAM safety
        step_duration = 30 
        all_srt_entries = []
        
        current_time = 0
        while current_time < total_duration:
            this_step_dur = min(step_duration, total_duration - current_time)
            
            # Load small slice
            audio, _ = librosa.load(str(temp_wav), sr=24000, offset=offset + current_time, duration=this_step_dur)
            
            if stt_config and current_time == 0:
                pad_left = int(stt_config.get("audio_silence_prefix_seconds", 0.0) * 24000)
                pad_right = int((stt_config.get("audio_delay_seconds", 0.0) + 1.0) * 24000)
                audio = np.pad(audio, (pad_left, pad_right), mode="constant")
            
            # Reset caches
            if hasattr(audio_tokenizer, "reset"): audio_tokenizer.reset()
            if hasattr(model, "transformer_cache"):
                for c in model.transformer_cache: c.reset()
            if hasattr(model, "depformer_cache"):
                for c in model.depformer_cache: c.reset()

            # Encode and Transcribe
            audio_tokens = audio_tokenizer.encode(audio[None, None, :])
            audio_tokens_mx = mx.array(audio_tokens)
            actual_steps = min(len(audio) // 1920, audio_tokens_mx.shape[1])
            
            gen = models.LmGen(
                model=model,
                max_steps=actual_steps + 10,
                text_sampler=utils.Sampler(temp=0.0),
                audio_sampler=utils.Sampler(temp=0.0),
                check=False,
            )
            
            chunk_tokens = []
            other_codebooks = lm_config.other_codebooks
            
            for idx in range(actual_steps):
                step_tokens = audio_tokens_mx[:, idx:idx+1, :other_codebooks]
                text_token = gen.step(step_tokens[0])
                text_token_id = text_token[0].item()
                mx.eval(gen.gen_sequence)
                
                delay = stt_config.get("audio_delay_seconds", 0.0) if stt_config else 0.0
                timestamp = (current_time + (idx * 0.08)) - delay
                chunk_tokens.append((max(0, timestamp), text_token_id))

            # Convert to SRT entries
            current_text = []
            start_time = None
            for timestamp, token_id in chunk_tokens:
                if token_id in (0, 3): continue
                char = text_tokenizer.id_to_piece(token_id).replace(" ", " ").replace("▁", " ")
                if char:
                    if start_time is None and char.strip(): start_time = timestamp
                    if start_time is not None: current_text.append(char)
                    if len(current_text) > 15 or any(p in char for p in ".!?"):
                        text_content = "".join(current_text).strip()
                        if text_content: all_srt_entries.append((start_time, timestamp + 0.08, text_content))
                        current_text, start_time = [], None
            
            if current_text and start_time is not None:
                all_srt_entries.append((start_time, chunk_tokens[-1][0] + 0.08, "".join(current_text).strip()))

            # Cleanup this chunk
            current_time += this_step_dur
            del audio, audio_tokens, audio_tokens_mx, gen, chunk_tokens
            mx.metal.clear_cache()
            gc.collect()

        if not all_srt_entries: return ""
        srt_content = ""
        for i, (start, end, text) in enumerate(all_srt_entries):
            srt_content += f"{i+1}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{text}\n\n"
        return srt_content

    except Exception as e:
        print(f"   ❌ Error transcribing {file_path.name}: {e}")
        return None
    finally:
        if temp_wav and temp_wav.exists():
            temp_wav.unlink()

def parse_srt(srt_content):
    entries = []
    blocks = re.split(r'\n\n+', srt_content.strip())
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            times = re.findall(r'(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if len(times) == 2:
                text = " ".join(lines[2:]).strip()
                entries.append({'start': times[0], 'end': times[1], 'text': text})
    return entries

def normalize_text(t):
    return re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()

def filter_full_show_transcription(full_srt_path, chronicle_srts, output_path):
    if not os.path.exists(full_srt_path): return
    try:
        with open(full_srt_path, 'r', encoding='utf-8') as f:
            full_content = f.read()
        full_entries = parse_srt(full_content)
        if not full_entries: return
        
        full_words = []
        word_to_entry = []
        for i, e in enumerate(full_entries):
            norm = normalize_text(e['text'])
            for w in norm.split():
                full_words.append(w)
                word_to_entry.append(i)
        
        def find_subsequence(seq, target, min_match=5):
            n = len(seq)
            for k in range(min(n, 12), min_match - 1, -1):
                for start in range(min(n - k + 1, 20)): # Check first 20 words for match
                    sub = seq[start:start+k]
                    for i in range(len(target) - k + 1):
                        if target[i:i+k] == sub:
                            return i
            return -1

        segments = []
        for start_srt, end_srt in chronicle_srts:
            start_norm = normalize_text(" ".join(e['text'] for e in parse_srt(start_srt)))
            end_norm = normalize_text(" ".join(e['text'] for e in parse_srt(end_srt)))
            
            start_words = start_norm.split()
            end_words = end_norm.split()
            
            if not start_words or not end_words: continue
            
            s_idx = find_subsequence(start_words, full_words)
            e_idx = -1
            if s_idx != -1:
                search_base = full_words[s_idx:]
                res = find_subsequence(end_words, search_base)
                if res != -1:
                    # Look at the end of the match
                    e_idx = s_idx + res + 5 # Approximate end
            else:
                # Try finding end without start
                e_idx = find_subsequence(end_words, full_words)

            if s_idx != -1 or e_idx != -1:
                start_entry = word_to_entry[s_idx] if s_idx != -1 else word_to_entry[max(0, e_idx - 100)]
                end_entry = word_to_entry[min(len(word_to_entry)-1, e_idx)] if e_idx != -1 else word_to_entry[min(len(word_to_entry)-1, s_idx + 100)]
                segments.append((start_entry, end_entry))

        if not segments:
            print("   ⚠️ No chronicles could be matched in the full show transcription.")
            return

        keep_indices = set()
        for start, end in segments:
            for i in range(min(start, end), max(start, end) + 1):
                keep_indices.add(i)
        
        filtered_entries = [full_entries[i] for i in sorted(list(keep_indices))]
        
        with open(output_path, "w", encoding="utf-8") as out:
            for i, entry in enumerate(filtered_entries):
                out.write(f"{i+1}\n{entry['start']} --> {entry['end']}\n{entry['text']}\n\n")
        print(f"   ✨ Cleaned transcription saved: {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"   ❌ Error filtering transcription: {e}")

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
    full_show_file = None
    if args.radio == "france-inter":
        files, full_show_file = scrape_radiofrance("france-inter", "franceinter", "07h00", target_date)
    elif args.radio == "france-info":
        files, full_show_file = scrape_radiofrance("france-info", "franceinfo", "06h00", target_date)
    elif args.radio == "france-culture":
        files, full_show_file = scrape_radiofrance("france-culture", "franceculture", "07h00", target_date)
    elif args.radio == "rtl":
        files, full_show_file = scrape_rtl(target_date)
        
    if not files and not full_show_file:
        print("ℹ️ No chronicles or full show found.")
        return

    print(f"✅ Found {len(files)} chronicles and {'a' if full_show_file else 'no'} full show. Initializing STT model...")
    
    # ... (Model initialization part remains same, I'll include it in the replace to be sure)
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
    base_out_dir = OUTPUT_BASE_DIR / RADIO_MAP[args.radio] / target_date
    chroniques_out_dir = base_out_dir / "chroniques"
    start_dir = chroniques_out_dir / "start_transcription"
    end_dir = chroniques_out_dir / "end_transcription"
    
    base_out_dir.mkdir(parents=True, exist_ok=True)
    start_dir.mkdir(parents=True, exist_ok=True)
    end_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📝 Transcribing and saving results to: {base_out_dir}")
    
    # 3.1 Full Show Transcription
    if full_show_file:
        print(f"⌛ Transcribing Full Show: {full_show_file.name}...")
        full_transcription = transcribe_segment(
            full_show_file, model, audio_tokenizer, text_tokenizer, lm_config, stt_config, 
            offset=0, duration=None
        )
        if full_transcription:
            out_path = base_out_dir / f"full_show_transcription.srt"
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(full_transcription)
            print(f"      ✅ Full show transcription saved: {out_path.name}")

    # 3.2 Chronicles Transcription
    results_count = 0
    chronicle_transcription_texts = []
    for f_path in tqdm(files, desc="Transcribing Chronicles", unit="file"):
        try:
            total_duration = get_audio_duration(f_path)
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
        
        if start_transcription and end_transcription:
            chronicle_transcription_texts.append((start_transcription, end_transcription))
            results_count += 1
        elif start_transcription or end_transcription:
            results_count += 1

    print(f"✨ Successfully processed {results_count}/{len(files)} chronicles.")
    
    # 3.3 Filtering Full Show Transcription
    if full_show_file and chronicle_transcription_texts:
        print(f"🧹 Filtering full show transcription to keep only chronicles...")
        full_srt_path = base_out_dir / "full_show_transcription.srt"
        filtered_srt_path = base_out_dir / "full_show_transcription_filtered.srt"
        filter_full_show_transcription(full_srt_path, chronicle_transcription_texts, filtered_srt_path)

    print(f"📂 Output saved in: {base_out_dir}")

if __name__ == "__main__":
    main()
