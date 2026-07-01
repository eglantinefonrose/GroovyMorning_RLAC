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

def format_timestamp(seconds, offset_seconds=0):
    td = timedelta(seconds=float(seconds + offset_seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

# --- Scraping Logic ---

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
    """Récupère l'URL .mp3 ou .m4a sur la page individuelle."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        response = requests.get(page_url, timeout=10, headers=headers)
        if response.status_code != 200: return None
        # On cherche l'URL media dans le texte de la page
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.(mp3|m4a)", response.text)
        return match.group(0) if match else None
    except:
        return None

def find_audio_anywhere(id_or_uuid, headers=None):
    """Cherche l'audio par tous les moyens possibles pour un identifiant donné (UUID)."""
    # 1. Tentative via l'API manifestation directe
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            url = data.get("url")
            if url and (".mp3" in url or ".m4a" in url): return url, data.get("title")
    except: pass

    # 2. Tentative via l'API player (v1)
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/player/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            sources = data.get("sources", [])
            for s in sources:
                if s.get("url") and (".mp3" in s["url"] or ".m4a" in s["url"]): return s["url"], data.get("title")
    except: pass

    return None, None

def scrape_radiofrance(brand, label_time, target_date, dry_run=False):
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
        
        # Build hash pour l'API
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"
        
        # Robust discovery logic (from reference script)
        match = re.search(rf'label:"{label_time}"[^}}]*id:"([a-f0-9-]{{36}})"', content)
        if not match:
            # Tentative alternative (format HTML attribut)
            match = re.search(rf'label="{label_time}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
            
        if not match:
            print(f"      ⚠️ Segment not found for {label_time} in grid.")
            return [], None

        show_id = match.group(1)
        
        # Extraction du lien principal
        link_match = re.search(rf'label[:=]"{label_time}".*?href[:=]"([^"]+)"', content, re.DOTALL)
        if not link_match:
            link_match = re.search(rf'label:"{label_time}".*?href:"([^"]+)"', content, re.DOTALL)
        main_link = link_match.group(1) if link_match else None

        full_show_path = None
        if main_link:
            # 1. Try robust discovery via API for full show
            full_audio_url, api_title = find_audio_anywhere(show_id, headers=headers)
            
            # 2. Fallback to page scraping
            if not full_audio_url:
                full_audio_url = get_audio_url_from_page(main_link, headers=headers)
                
            if full_audio_url:
                ext = "m4a" if ".m4a" in full_audio_url.lower() else "mp3"
                dest_path = radio_dir / f"full_show.{ext}"
                if download_file(full_audio_url, dest_path, headers=headers, dry_run=dry_run):
                    if not dry_run: print(f"      ✅ Downloaded Full Show: {dest_path.name}")
                    full_show_path = dest_path

        # API call to get chronicles using the show_id we found
        payload_raw = [{"brand": 1, "parentStep": 2}, clean_brand, show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"
        
        api_resp = requests.get(api_url, headers=headers, timeout=10)
        downloaded_files = []
        if api_resp.status_code == 200:
            result_data = api_resp.json()
            result_str = str(result_data.get("result", ""))
            
            # Match podcasts links
            podcast_links = list(set(re.findall(rf'/(?:{clean_brand}|{brand})/podcasts/[^"\s\\]+', result_str)))
            print(f"   [*] Discovered {len(podcast_links)} chronicle links via API.")
            
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
        else:
            print(f"      ⚠️ Chronicles API call failed (status {api_resp.status_code})")
            
        # fallback check for existing emission file
        if not full_show_path:
            for pattern in ["full_show.*", "*Emission*", "*Matinale*", "*7-10*"]:
                for existing in radio_dir.glob(pattern):
                    if existing.suffix.lower() in ['.mp3', '.m4a']:
                        print(f"   [*] Found existing full show file: {existing.name}")
                        full_show_path = existing
                        break
                if full_show_path: break
                
        return downloaded_files, full_show_path
    except Exception as e:
        print(f"   ❌ Error scraping {brand}: {e}")
        return [], None

def scrape_rtl(target_date_str, dry_run=False):
    FEEDS = [
        ("b799ffaa-ccee-4a9a-a75f-0137a5787288", "laurent-gerra"),
        ("bd84bb2f-2f24-44a5-87ec-4851ba856c6a", "l-invite-de-rtl"),
        ("01a5bd92-d6c8-4572-8092-88e4c9953cc9", "l-oeil-de-philippe-caveriviere"),
        ("aeb105e8-907f-4710-b9d9-54ba21ca6e8c", "rtl-matin"),
    ]
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
                    dt = datetime.strptime(pub_date_str[:16], "%a, %d %b %Y")
                except: continue
                
                if dt.date() == target_date.date():
                    enclosure = item.find('enclosure')
                    if enclosure is None: continue
                    audio_url = enclosure.get('url')
                    
                    title = item.find('title').text
                    is_integrale = ("INTÉGRALE" in title.upper() or "RTL MATIN DU" in title.upper())
                    
                    if is_integrale:
                        dest_dir = MEDIA_DIR / radio_dir_name / target_date_str
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / "full_show.mp3"
                        if download_file(audio_url, dest_path, dry_run=dry_run):
                            if not dry_run: print(f"      ✅ Downloaded Full Show: {title}")
                            full_show_file = dest_path
                    else:
                        dest_dir = MEDIA_DIR / radio_dir_name / target_date_str / "chroniques"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                        dest_path = dest_dir / f"{clean_title}.mp3"
                        
                        if download_file(audio_url, dest_path, dry_run=dry_run):
                            print(f"      ✅ Downloaded: {clean_title}")
                            downloaded_files.append(dest_path)
        except Exception as e:
            print(f"   ❌ Error scraping RTL feed {feed_slug}: {e}")
            
    if not full_show_file:
        rtl_dir = MEDIA_DIR / RADIO_MAP["rtl"] / target_date_str
        for existing in rtl_dir.glob("*.mp3"):
            if existing.name == f"{target_date_str}.mp3" or "integrale" in existing.name.lower() or existing.name == "full_show.mp3":
                print(f"   [*] Found existing RTL integrale: {existing.name}")
                full_show_file = existing
                break

    return downloaded_files, full_show_file

# --- Transcription Logic ---

import gc
mx.metal.set_cache_limit(4 * 1024 * 1024 * 1024)

def transcribe_segment(file_path, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=0, duration=None):
    temp_wav = None
    try:
        print(f"   [*] Preparing audio for {file_path.name} (offset: {offset}, duration: {duration})...")
        
        audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
        model.transformer_cache = model.transformer.make_rot_cache()
        if hasattr(model, "depformer_cache") and model.depformer.slices:
            model.depformer_cache = model.depformer.slices[0].transformer.make_cache()
        mx.eval(model.transformer_cache)

        temp_wav = file_path.with_suffix(f".{os.getpid()}.temp.wav")
        conv_cmd = [
            "ffmpeg", "-i", str(file_path),
            "-ar", "24000", "-ac", "1", 
            "-y", str(temp_wav), "-loglevel", "error"
        ]
        subprocess.run(conv_cmd, check=True)

        total_duration = get_audio_duration(temp_wav)
        if duration is not None:
            total_duration = min(total_duration, duration)

        print(f"   [*] Transcribing {total_duration:.2f}s of {file_path.name}...")

        step_duration = 30 
        all_srt_entries = []
        
        current_time = 0
        while current_time < total_duration:
            this_step_dur = min(step_duration, total_duration - current_time)
            print(f"      [*] Chunk {current_time:.0f}-{current_time+this_step_dur:.0f}s...", end="", flush=True)
            
            audio, _ = librosa.load(str(temp_wav), sr=24000, offset=offset + current_time, duration=this_step_dur)
            
            if stt_config and current_time == 0:
                pad_left = int(stt_config.get("audio_silence_prefix_seconds", 0.0) * 24000)
                pad_right = int((stt_config.get("audio_delay_seconds", 0.0) + 1.0) * 24000)
                audio = np.pad(audio, (pad_left, pad_right), mode="constant")
            
            audio_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
            model.transformer_cache = model.transformer.make_rot_cache()
            if hasattr(model, "depformer_cache") and model.depformer.slices:
                model.depformer_cache = model.depformer.slices[0].transformer.make_cache()
            mx.eval(model.transformer_cache)

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
                timestamp = (current_time + (idx * 0.08)) - delay
                chunk_tokens.append((max(0, timestamp), text_token[0].item()))
            
            print(" done.")

            current_text = []
            for timestamp, token_id in chunk_tokens:
                if token_id in (0, 3): continue
                char = text_tokenizer.id_to_piece(token_id).replace(" ", " ").replace("▁", " ")
                if char:
                    current_text.append(char)
                    if any(p in char for p in ".!?"):
                        all_srt_entries.append("".join(current_text).strip())
                        current_text = []
            
            if current_text:
                all_srt_entries.append("".join(current_text).strip())

            current_time += this_step_dur
            del audio, gen, chunk_tokens
            mx.metal.clear_cache()
            gc.collect()

        if not all_srt_entries: return ""
        return " ".join(all_srt_entries)

    except Exception as e:
        print(f"   ❌ Error transcribing {file_path.name}: {e}")
        return None
    finally:
        if temp_wav and temp_wav.exists():
            temp_wav.unlink()

def normalize_text(t):
    return re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()

def filter_full_show_transcription(full_txt_path, chronicle_texts, output_path):
    if not os.path.exists(full_txt_path): return
    try:
        with open(full_txt_path, 'r', encoding='utf-8') as f:
            full_content = f.read()
        
        full_words = full_content.split()
        if not full_words: return
        
        def find_subsequence(seq, target, min_match=6):
            n = len(seq)
            for k in range(min(n, 15), min_match - 1, -1):
                sub = seq[:k]
                for i in range(len(target) - k + 1):
                    target_sub = [normalize_text(w) for w in target[i:i+k]]
                    seq_sub = [normalize_text(w) for w in sub]
                    if target_sub == seq_sub:
                        return i
            return -1

        segments = []
        for start_txt, end_txt in chronicle_texts:
            start_words = start_txt.split()
            end_words = end_txt.split()
            if not start_words or not end_words: continue
            
            s_idx = find_subsequence(start_words, full_words)
            search_base = full_words[s_idx:] if s_idx != -1 else full_words
            e_rel_idx = find_subsequence(end_words, search_base)
            
            e_idx = -1
            if e_rel_idx != -1:
                e_idx = (s_idx if s_idx != -1 else 0) + e_rel_idx + len(end_words[:10])

            if s_idx != -1 or e_idx != -1:
                start_final = s_idx if s_idx != -1 else max(0, e_idx - 1500)
                end_final = e_idx if e_idx != -1 else min(len(full_words), start_final + 1500)
                segments.append((start_final, end_final))

        if not segments:
            print("   ⚠️ No chronicles could be matched in the full show transcription.")
            return

        keep_indices = set()
        for start, end in segments:
            for i in range(max(0, start - 5), min(len(full_words), end + 5)):
                keep_indices.add(i)
        
        filtered_words = []
        last_idx = -1
        for i in sorted(list(keep_indices)):
            if last_idx != -1 and i > last_idx + 1:
                filtered_words.append("\n\n--- [TRUNCATED] ---\n\n")
            filtered_words.append(full_words[i])
            last_idx = i
            
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(" ".join(filtered_words))
        print(f"   ✨ Cleaned transcription saved: {os.path.basename(output_path)}")
        
    except Exception as e:
        print(f"   ❌ Error filtering transcription: {e}")

# --- Core Execution Function ---

def process_single_date(radio, target_date, duration, model, mimi_path, text_tokenizer, lm_config, stt_config, dry_run=False):
    """Processes a single date for a given radio using a pre-loaded model."""
    print(f"\n--- Processing {radio} for {target_date} ---")
    
    # 1. Scraping
    files = []
    full_show_file = None
    if radio == "rtl":
        files, full_show_file = scrape_rtl(target_date, dry_run=dry_run)
    else:
        label = "06h00" if radio == "france-info" else "07h00"
        files, full_show_file = scrape_radiofrance(radio, label, target_date, dry_run=dry_run)
        
    if dry_run:
        print(f"   [DRY-RUN] Found {len(files)} chronicles and {'a' if full_show_file else 'no'} full show.")
        return True

    # NEW: Supplement with already present files in the directory
    radio_dir_name = RADIO_MAP.get(radio)
    if radio_dir_name:
        chroniques_local_dir = MEDIA_DIR / radio_dir_name / target_date / "chroniques"
        if chroniques_local_dir.exists():
            local_files = [f for f in chroniques_local_dir.glob("*") if f.suffix.lower() in ['.mp3', '.m4a']]
            existing_paths = {str(f.absolute()) for f in files}
            for lf in local_files:
                if str(lf.absolute()) not in existing_paths:
                    files.append(lf)
    
    if not files and not full_show_file:
        print(f"   ℹ️ No files found for {target_date}. Skipping.")
        return False

    # 3. Transcription
    base_out_dir = OUTPUT_BASE_DIR / RADIO_MAP[radio] / target_date
    chroniques_out_dir = base_out_dir / "chroniques"
    start_dir = chroniques_out_dir / "start_transcription"
    end_dir = chroniques_out_dir / "end_transcription"
    
    base_out_dir.mkdir(parents=True, exist_ok=True)
    start_dir.mkdir(parents=True, exist_ok=True)
    end_dir.mkdir(parents=True, exist_ok=True)
    
    # 3.1 Full Show Transcription
    if full_show_file:
        print(f"⌛ Transcribing Full Show: {full_show_file.name}...")
        full_transcription = transcribe_segment(full_show_file, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=0, duration=None)
        if full_transcription:
            out_path = base_out_dir / "full_show_transcription.txt"
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(full_transcription)
            print(f"      ✅ Full show transcription saved: {out_path.name}")

    # 3.2 Chronicles Transcription
    chronicle_transcription_texts = []
    for i, f_path in enumerate(files):
        print(f"   [{i+1}/{len(files)}] Processing {f_path.name}...")
        try:
            total_duration = get_audio_duration(f_path)
        except: continue

        # Transcribe Start
        start_transcription = transcribe_segment(f_path, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=0, duration=duration)
        if start_transcription:
            with open(start_dir / f"{f_path.stem}_start.txt", "w", encoding="utf-8") as out:
                out.write(start_transcription)
        
        # Transcribe End
        end_offset = max(0, total_duration - duration)
        end_transcription = transcribe_segment(f_path, model, mimi_path, text_tokenizer, lm_config, stt_config, offset=end_offset, duration=duration)
        if end_transcription:
            with open(end_dir / f"{f_path.stem}_end.txt", "w", encoding="utf-8") as out:
                out.write(end_transcription)
        
        if start_transcription and end_transcription:
            chronicle_transcription_texts.append((start_transcription, end_transcription))

    # 3.3 Filtering
    if full_show_file and chronicle_transcription_texts:
        print(f"🧹 Filtering full show transcription...")
        filter_full_show_transcription(base_out_dir / "full_show_transcription.txt", chronicle_transcription_texts, base_out_dir / "full_show_transcription_filtered.txt")

    print(f"✨ Done for {target_date}.")
    return True

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Scrape and transcribe full show + chronicles.")
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"], help="Radio station slug")
    parser.add_argument("--date", type=str, help="Target date in DD-MM-YYYY format (default: today)")
    parser.add_argument("--duration", type=int, default=30, help="Duration to transcribe for segments in seconds (default: 30)")
    parser.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID, help=f"Hugging Face model ID")
    parser.add_argument("--dry-run", action="store_true", help="Show URLs without downloading or transcribing")
    
    args = parser.parse_args()
    target_date = args.date if args.date else datetime.now().strftime("%d-%m-%Y")
    
    print(f"🚀 Starting process for {args.radio} on {target_date}...")
    
    if args.dry_run:
        process_single_date(args.radio, target_date, args.duration, None, None, None, None, None, dry_run=True)
        return

    # Initialize model
    print(f"   Initializing STT model...")
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

    process_single_date(args.radio, target_date, args.duration, model, mimi_path, text_tokenizer, lm_config, stt_config)

if __name__ == "__main__":
    main()
