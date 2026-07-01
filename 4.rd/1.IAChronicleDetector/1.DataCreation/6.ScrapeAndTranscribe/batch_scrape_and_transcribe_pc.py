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

# --- PC-Compatible Transcription (Whisper) ---
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("❌ Error: 'faster-whisper' is not installed.")
    print("Please install it with: pip install faster-whisper")
    sys.exit(1)

# --- Configuration & Paths ---

# For the PC version, we use local relative paths by default to ensure portability
BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media" / "audio"
OUTPUT_BASE_DIR = BASE_DIR / "transcriptions_whisper"

# Mapping between radio parameter and directory names
RADIO_MAP = {
    "france-inter": "4.franceinter-matin",
    "rtl": "5.rtl-matin",
    "france-info": "2.franceinfo-matin",
    "france-culture": "3.franceculture-matin",
}

def get_audio_duration(file_path):
    """Get duration of an audio file using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"      ⚠️ Could not get duration for {file_path}: {e}")
        return 0

# --- Scraping Logic ---

def download_file(url, dest_path, headers=None, dry_run=False):
    if url.startswith('//'): url = 'https:' + url
    
    if dry_run:
        print(f"      [DRY-RUN] Would download: {url}")
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

def find_audio_anywhere(id_or_uuid, headers=None):
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            url = data.get("url")
            if url and (".mp3" in url or ".m4a" in url): return url, data.get("title")
    except: pass

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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
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
            return [], None
        content = resp.text
        
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"
        
        match = re.search(rf'label:"{label_time}"[^}}]*id:"([a-f0-9-]{{36}})"', content)
        if not match:
            match = re.search(rf'label="{label_time}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
            
        if not match:
            print(f"      ⚠️ Segment not found for {label_time} in grid.")
            return [], None

        show_id = match.group(1)
        link_match = re.search(rf'label[:=]"{label_time}".*?href[:=]"([^"]+)"', content, re.DOTALL)
        if not link_match:
            link_match = re.search(rf'label:"{label_time}".*?href:"([^"]+)"', content, re.DOTALL)
        main_link = link_match.group(1) if link_match else None

        full_show_path = None
        if main_link:
            full_audio_url, _ = find_audio_anywhere(show_id, headers=headers)
            if not full_audio_url:
                full_audio_url = get_audio_url_from_page(main_link, headers=headers)
                
            if full_audio_url:
                ext = "m4a" if ".m4a" in full_audio_url.lower() else "mp3"
                dest_path = radio_dir / f"full_show.{ext}"
                if download_file(full_audio_url, dest_path, headers=headers, dry_run=dry_run):
                    full_show_path = dest_path

        payload_raw = [{"brand": 1, "parentStep": 2}, clean_brand, show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"
        
        api_resp = requests.get(api_url, headers=headers, timeout=10)
        downloaded_files = []
        if api_resp.status_code == 200:
            result_data = api_resp.json()
            result_str = str(result_data.get("result", ""))
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
    except: return [], None
        
    downloaded_files = []
    full_show_file = None
    radio_dir_name = RADIO_MAP["rtl"]
    
    for feed_id, feed_slug in FEEDS:
        feed_url = f"https://feeds.audiomeans.fr/feed/{feed_id}.xml"
        try:
            resp = requests.get(feed_url, timeout=20)
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
                            full_show_file = dest_path
                    else:
                        dest_dir = MEDIA_DIR / radio_dir_name / target_date_str / "chroniques"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        clean_title = re.sub(r'[^a-z0-9]', '-', title.lower())[:50].strip('-')
                        dest_path = dest_dir / f"{clean_title}.mp3"
                        if download_file(audio_url, dest_path, dry_run=dry_run):
                            downloaded_files.append(dest_path)
        except: pass
    return downloaded_files, full_show_file

# --- Transcription Logic (PC version using Faster-Whisper) ---

def transcribe_segment_whisper(file_path, model, offset=0, duration=None):
    """Transcribes a segment of an audio file using Faster-Whisper."""
    try:
        # We use ffmpeg via subprocess to extract the segment if needed to save memory/time
        # Or we can just let librosa/faster-whisper handle it, but for very large files, 
        # pre-cutting with ffmpeg is safer on PC.
        
        temp_segment = file_path.parent / f"temp_{os.getpid()}_{file_path.stem}.wav"
        
        cmd = ["ffmpeg", "-y", "-ss", str(offset)]
        if duration:
            cmd.extend(["-t", str(duration)])
        cmd.extend(["-i", str(file_path), "-ar", "16000", "-ac", "1", str(temp_segment), "-loglevel", "error"])
        
        subprocess.run(cmd, check=True)
        
        segments, info = model.transcribe(str(temp_segment), beam_size=5, language="fr")
        
        text = " ".join([seg.text for seg in segments]).strip()
        
        if temp_segment.exists():
            temp_segment.unlink()
            
        return text
    except Exception as e:
        print(f"   ❌ Error transcribing {file_path.name}: {e}")
        return None

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
                    if target_sub == seq_sub: return i
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

        if not segments: return

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

# --- Execution ---

def process_single_date(radio, target_date, duration, model, dry_run=False):
    print(f"\n--- Processing {radio} for {target_date} ---")
    
    if radio == "rtl":
        files, full_show_file = scrape_rtl(target_date, dry_run=dry_run)
    else:
        label = "06h00" if radio == "france-info" else "07h00"
        files, full_show_file = scrape_radiofrance(radio, label, target_date, dry_run=dry_run)
        
    if dry_run:
        print(f"   [DRY-RUN] Found {len(files)} chronicles and {'a' if full_show_file else 'no'} full show.")
        return

    # Check for existing local files
    radio_dir_name = RADIO_MAP.get(radio)
    if radio_dir_name:
        chron_dir = MEDIA_DIR / radio_dir_name / target_date / "chroniques"
        if chron_dir.exists():
            for lf in chron_dir.glob("*"):
                if lf.suffix.lower() in ['.mp3', '.m4a'] and lf not in files:
                    files.append(lf)
    
    if not files and not full_show_file:
        print(f"   ℹ️ No files found. Skipping.")
        return

    base_out_dir = OUTPUT_BASE_DIR / RADIO_MAP[radio] / target_date
    chron_out = base_out_dir / "chroniques"
    base_out_dir.mkdir(parents=True, exist_ok=True)
    chron_out.mkdir(parents=True, exist_ok=True)
    
    # Full Show
    if full_show_file:
        print(f"⌛ Transcribing Full Show: {full_show_file.name}...")
        txt = transcribe_segment_whisper(full_show_file, model)
        if txt:
            with open(base_out_dir / "full_show_transcription.txt", "w", encoding="utf-8") as out:
                out.write(txt)

    # Chronicles (Start and End for matching)
    chronicle_transcription_texts = []
    for i, f_path in enumerate(files):
        print(f"   [{i+1}/{len(files)}] {f_path.name}...")
        total_dur = get_audio_duration(f_path)
        
        start_txt = transcribe_segment_whisper(f_path, model, offset=0, duration=duration)
        end_txt = transcribe_segment_whisper(f_path, model, offset=max(0, total_dur - duration), duration=duration)
        
        if start_txt and end_txt:
            chronicle_transcription_texts.append((start_txt, end_txt))
            with open(chron_out / f"{f_path.stem}_start.txt", "w", encoding="utf-8") as out: out.write(start_txt)
            with open(chron_out / f"{f_path.stem}_end.txt", "w", encoding="utf-8") as out: out.write(end_txt)

    if full_show_file and chronicle_transcription_texts:
        filter_full_show_transcription(base_out_dir / "full_show_transcription.txt", chronicle_transcription_texts, base_out_dir / "full_show_transcription_filtered.txt")

def main():
    parser = argparse.ArgumentParser(description="PC Batch Scrape and Transcribe (Whisper)")
    parser.add_argument("radio", choices=["france-inter", "rtl", "france-info", "france-culture"])
    parser.add_argument("start_date", help="DD-MM-YYYY")
    parser.add_argument("end_date", help="DD-MM-YYYY")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--model-size", default="small", help="Whisper model size (tiny, base, small, medium, large-v3)")
    parser.add_argument("--device", default="auto", help="cpu, cuda, or auto")
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    try:
        start_dt = datetime.strptime(args.start_date, "%d-%m-%Y")
        end_dt = datetime.strptime(args.end_date, "%d-%m-%Y")
    except:
        print("❌ Invalid date format.")
        return

    model = None
    if not args.dry_run:
        print(f"🚀 Initializing Whisper ({args.model_size}) on {args.device}...")
        # device="auto" will use CUDA if available, else CPU
        model = WhisperModel(args.model_size, device=args.device, compute_type="float32" if args.device == "cpu" else "float16")

    curr_dt = start_dt
    while curr_dt <= end_dt:
        if args.radio == "france-inter" and curr_dt.weekday() > 3:
            pass # Skip weekends for Inter
        else:
            process_single_date(args.radio, curr_dt.strftime("%d-%m-%Y"), args.duration, model, dry_run=args.dry_run)
        curr_dt += timedelta(days=1)
    
    print("\n✨ Finished.")

if __name__ == "__main__":
    main()
