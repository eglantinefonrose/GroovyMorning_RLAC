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
from tqdm import tqdm

# --- Kyutai STT for PC (PyTorch version) ---
try:
    import torch
    import rustymimi
    import sentencepiece
    from moshi import models
    from huggingface_hub import hf_hub_download
    import librosa
    import numpy as np
except ImportError as e:
    print(f"❌ Error: Missing dependencies ({e}).")
    print("Please install them with: pip install torch moshi rustymimi sentencepiece huggingface_hub librosa numpy")
    sys.exit(1)

# --- Configuration & Paths ---

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media" / "audio"
OUTPUT_BASE_DIR = BASE_DIR / "transcriptions_kyutai"

DEFAULT_MODEL_ID = "kyutai/stt-1b-en_fr"

RADIO_MAP = {
    "france-inter": "4.franceinter-matin",
    "rtl": "5.rtl-matin",
    "france-info": "2.franceinfo-matin",
    "france-culture": "3.franceculture-matin",
}

def get_audio_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return 0

# --- Scraping Logic ---

def download_file(url, dest_path, headers=None, dry_run=False):
    if url.startswith('//'): url = 'https:' + url
    if dry_run: return True
    if os.path.exists(dest_path): return True
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        return True
    except: return False

def get_audio_url_from_page(page_url, headers=None):
    try:
        if page_url.startswith('/'): page_url = f"https://www.radiofrance.fr{page_url}"
        response = requests.get(page_url, timeout=10, headers=headers)
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.(mp3|m4a)", response.text)
        return match.group(0) if match else None
    except: return None

def find_audio_anywhere(id_or_uuid, headers=None):
    for api_tpl in ["https://www.radiofrance.fr/api/v1/manifestations/{}", "https://www.radiofrance.fr/api/v1/player/manifestations/{}"]:
        try:
            resp = requests.get(api_tpl.format(id_or_uuid), timeout=5, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("url") or (data.get("sources", [{}])[0].get("url"))
                if url and (".mp3" in url or ".m4a" in url): return url, data.get("title")
        except: continue
    return None, None

def scrape_radiofrance(brand, label_time, target_date, dry_run=False):
    headers = {'User-Agent': 'Mozilla/5.0'}
    radio_dir = MEDIA_DIR / RADIO_MAP[brand] / target_date
    chroniques_dir = radio_dir / "chroniques"
    chroniques_dir.mkdir(parents=True, exist_ok=True)
    
    grid_url = f"https://www.radiofrance.fr/{brand.replace('-', '')}/grille-programmes?date={target_date}"
    try:
        content = requests.get(grid_url, timeout=10, headers=headers).text
        build_hash = (re.search(r"\"buildId\":\"([^\"]+)\"", content) or [None, "1vzv7fl"])[1]
        show_id = (re.search(rf'label:"{label_time}"[^}}]*id:"([a-f0-9-]{{36}})"', content) or re.search(rf'label="{label_time}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)).group(1)
        main_link = (re.search(rf'label[:=]"{label_time}".*?href[:=]"([^"]+)"', content, re.DOTALL)).group(1)

        full_show_path = None
        url, _ = find_audio_anywhere(show_id, headers=headers)
        if not url: url = get_audio_url_from_page(main_link, headers=headers)
        if url:
            dest = radio_dir / f"full_show.{'m4a' if '.m4a' in url.lower() else 'mp3'}"
            if download_file(url, dest, headers=headers, dry_run=dry_run): full_show_path = dest

        payload_b64 = base64.b64encode(json.dumps([{"brand": 1, "parentStep": 2}, brand.replace('-', ''), show_id], separators=(',', ':')).encode()).decode()
        api_resp = requests.get(f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}", headers=headers, timeout=10)
        downloaded = []
        if api_resp.status_code == 200:
            for link in set(re.findall(rf'/(?:{brand.replace("-","")}|{brand})/podcasts/[^"\s\\]+', str(api_resp.json().get("result", "")))):
                if main_link and main_link in link: continue
                url = get_audio_url_from_page(link, headers=headers)
                if url:
                    dest = chroniques_dir / f"{link.split('/')[3]}.{'m4a' if '.m4a' in url.lower() else 'mp3'}"
                    if download_file(url, dest, headers=headers, dry_run=dry_run): downloaded.append(dest)
        return downloaded, full_show_path
    except: return [], None

def scrape_rtl(target_date_str, dry_run=False):
    FEEDS = [("b799ffaa-ccee-4a9a-a75f-0137a5787288", "laurent-gerra"), ("bd84bb2f-2f24-44a5-87ec-4851ba856c6a", "l-invite-de-rtl"), ("01a5bd92-d6c8-4572-8092-88e4c9953cc9", "l-oeil-de-philippe-caveriviere"), ("aeb105e8-907f-4710-b9d9-54ba21ca6e8c", "rtl-matin")]
    try: target_date = datetime.strptime(target_date_str, "%d-%m-%Y")
    except: return [], None
    downloaded, full_show = [], None
    for f_id, _ in FEEDS:
        try:
            feed_url = f"https://feeds.audiomeans.fr/feed/{f_id}.xml"
            root = ET.fromstring(requests.get(feed_url, timeout=20).content)
            for item in root.findall('.//item'):
                pub_date = item.find('pubDate').text[:16]
                if datetime.strptime(pub_date, "%a, %d %b %Y").date() == target_date.date():
                    url = item.find('enclosure').get('url')
                    title = item.find('title').text
                    if "INTÉGRALE" in title.upper() or "RTL MATIN DU" in title.upper():
                        dest = MEDIA_DIR / RADIO_MAP["rtl"] / target_date_str / "full_show.mp3"
                        if download_file(url, dest, dry_run=dry_run): full_show = dest
                    else:
                        clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                        dest = MEDIA_DIR / RADIO_MAP["rtl"] / target_date_str / "chroniques" / f"{clean_title}.mp3"
                        if download_file(url, dest, dry_run=dry_run): downloaded.append(dest)
        except: pass
    return downloaded, full_show

# --- Kyutai STT Logic (PyTorch) ---

def transcribe_segment_kyutai(file_path, model, audio_tokenizer, text_tokenizer, device, offset=0, duration=None):
    try:
        temp_wav = file_path.parent / f"temp_{os.getpid()}.wav"
        cmd = ["ffmpeg", "-y", "-ss", str(offset)]
        if duration: cmd.extend(["-t", str(duration)])
        cmd.extend(["-i", str(file_path), "-ar", "24000", "-ac", "1", str(temp_wav), "-loglevel", "error"])
        subprocess.run(cmd, check=True)

        audio, _ = librosa.load(str(temp_wav), sr=24000)
        if temp_wav.exists(): temp_wav.unlink()

        audio_tensor = torch.from_numpy(audio).to(device).unsqueeze(0).unsqueeze(0)
        
        from moshi.models import LMGen
        from moshi.utils import Sampler
        
        with torch.no_grad():
            codes = audio_tokenizer.encode(audio_tensor)
            gen = LMGen(model, device=device, text_sampler=Sampler(temp=0.0), audio_sampler=Sampler(temp=0.0))
            
            tokens = []
            steps = codes.shape[-1]
            for i in range(steps):
                input_codes = codes[:, :, i:i+1]
                text_token = gen.step(input_codes[0])
                token_id = text_token[0].item()
                if token_id not in (0, 3):
                    tokens.append(token_id)

        text = ""
        for tid in tokens:
            piece = text_tokenizer.id_to_piece(tid).replace(" ", " ").replace("▁", "")
            text += piece
        return text.strip()
    except Exception as e:
        print(f"   ❌ Transcription error: {e}")
        return None

def process_single_date(radio, target_date, duration, model, audio_tokenizer, text_tokenizer, device, dry_run=False):
    print(f"\n--- {radio} | {target_date} ---")
    files, full_show = scrape_rtl(target_date, dry_run) if radio == "rtl" else scrape_radiofrance(radio, "06h00" if radio == "france-info" else "07h00", target_date, dry_run)
    if dry_run or (not files and not full_show): return

    base_out = OUTPUT_BASE_DIR / RADIO_MAP[radio] / target_date
    base_out.mkdir(parents=True, exist_ok=True)
    (base_out / "chroniques").mkdir(parents=True, exist_ok=True)

    if full_show:
        print(f"⌛ Full Show...")
        txt = transcribe_segment_kyutai(full_show, model, audio_tokenizer, text_tokenizer, device)
        if txt: (base_out / "full_show_transcription.txt").write_text(txt, encoding='utf-8')

    for f in files:
        print(f"   🎙️ {f.name}")
        total = get_audio_duration(f)
        s_txt = transcribe_segment_kyutai(f, model, audio_tokenizer, text_tokenizer, device, 0, duration)
        e_txt = transcribe_segment_kyutai(f, model, audio_tokenizer, text_tokenizer, device, max(0, total-duration), duration)
        if s_txt and e_txt:
            (base_out / "chroniques" / f"{f.stem}_start.txt").write_text(s_txt, encoding='utf-8')
            (base_out / "chroniques" / f"{f.stem}_end.txt").write_text(e_txt, encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"])
    parser.add_argument("start_date")
    parser.add_argument("end_date")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model, audio_tokenizer, text_tokenizer = None, None, None
    if not args.dry_run:
        print(f"🚀 Loading Kyutai STT on {args.device}...")
        from moshi.models import loaders
        
        # CheckpointInfo is the standard way to load models in the PyTorch version
        checkpoint = loaders.CheckpointInfo.from_hf_repo(args.model_id)
        
        # Load components
        model = checkpoint.get_moshi(device=args.device)
        model.eval()
        
        audio_tokenizer = checkpoint.get_mimi(device=args.device)
        audio_tokenizer.eval()
        
        # In the PyTorch version, it's often a property or needs a specific loader
        try:
            text_tokenizer = checkpoint.get_text_tokenizer()
        except:
            import sentencepiece
            text_tokenizer = sentencepiece.SentencePieceProcessor(checkpoint.tokenizer)

    curr = datetime.strptime(args.start_date, "%d-%m-%Y")
    end = datetime.strptime(args.end_date, "%d-%m-%Y")
    while curr <= end:
        if not (args.radio == "france-inter" and curr.weekday() > 3):
            process_single_date(args.radio, curr.strftime("%d-%m-%Y"), args.duration, model, audio_tokenizer, text_tokenizer, args.device, args.dry_run)
        curr += timedelta(days=1)

if __name__ == "__main__":
    main()
