import os
import re
import requests
import sys
import base64
import json
from datetime import datetime, timedelta

def download_file(url, dest_path, headers=None):
    """Télécharge un fichier si il n'existe pas déjà."""
    if os.path.exists(dest_path):
        print(f"      ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    
    print(f"      📥 Téléchargement : {url}")
    try:
        if url.startswith('//'): url = 'https:' + url
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"      ✅ Sauvegardé.")
        return True
    except Exception as e:
        print(f"      ❌ Erreur : {e}")
        return False

def get_audio_url_from_page(page_url, headers=None):
    """Récupère l'URL .mp3 sur la page individuelle."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        response = requests.get(page_url, timeout=10, headers=headers)
        if response.status_code != 200: return None
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.mp3", response.text)
        return match.group(0) if match else None
    except:
        return None

def find_audio_anywhere(id_or_uuid, headers=None):
    """Cherche l'audio par tous les moyens possibles pour un identifiant donné."""
    # 1. Tentative via l'API manifestation directe
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            url = data.get("url")
            if url and ".mp3" in url: return url, data.get("title")
    except: pass

    # 2. Tentative via l'API player (v1)
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/player/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            sources = data.get("sources", [])
            for s in sources:
                if s.get("url") and ".mp3" in s["url"]: return s["url"], data.get("title")
    except: pass

    return None, None

def process_date(target_date):
    """Exécute la logique complète pour une date donnée."""
    print(f"\n[*] --- TRAITEMENT DU {target_date} ---")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'}
    
    dest_dir = f"../../../../@assets/0.media/audio/2.franceinfo-matin/{target_date}"
    chroniques_dir = os.path.join(dest_dir, "chroniques")
    os.makedirs(chroniques_dir, exist_ok=True)

    grid_url = f"https://www.radiofrance.fr/franceinfo/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10, headers=headers)
        if resp.status_code != 200: return
        content = resp.text

        # Build hash
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"

        processed_shows = set()

        for label in ["06h00"]:
            match = re.search(rf'label="{label}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
            if not match: continue
            
            show_id = match.group(1)
            
            if show_id in processed_shows: continue
            processed_shows.add(show_id)

            link_match = re.search(rf'label="{label}".*?<a href="([^"]+)"[^>]*data-testid="Link"[^>]*>(.*?)</a>', content, re.DOTALL)
            if not link_match: continue
            main_link, show_title = link_match.groups()
            show_title = re.sub('<[^>]*>', '', show_title).strip()

            print(f"   [*] Segment trouvé : {show_title} ({label})")

            # 1. Téléchargement de l'intégrale à la RACINE
            main_audio_url = get_audio_url_from_page(main_link, headers=headers)
            if main_audio_url:
                dest_name = f"{target_date}.mp3" if "06h00" in label else f"{re.sub(r'[^a-z0-9]', '-', show_title.lower())}.mp3"
                download_file(main_audio_url, os.path.join(dest_dir, dest_name), headers=headers)

            # 2. Appel API Chroniques
            payload_raw = [{"brand": 1, "parentStep": 2}, "franceinfo", show_id]
            payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
            api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

            api_resp = requests.get(api_url, headers=headers, timeout=10)
            if api_resp.status_code == 200:
                result_str = api_resp.json().get("result", "")
                
                podcast_links = list(set(re.findall(r'/franceinfo/podcasts/[^"\\]+', result_str)))
                potential_ids = list(set(re.findall(r'[:",](\d{7,8})[:",]', result_str)))
                uuids = list(set(re.findall(r'[a-f0-9-]{36}', result_str)))
                
                processed_urls = {main_audio_url} if main_audio_url else set()

                for link in sorted(podcast_links):
                    if link == main_link: continue
                    parts = link.split('/')
                    show_name = parts[3] if len(parts) > 3 else "chronique"
                    audio_url = get_audio_url_from_page(link, headers=headers)
                    if audio_url and audio_url not in processed_urls:
                        if download_file(audio_url, os.path.join(chroniques_dir, f"{show_name}.mp3"), headers=headers):
                            processed_urls.add(audio_url)

                for target in sorted(uuids + potential_ids):
                    if target == show_id: continue
                    audio_url, title = find_audio_anywhere(target, headers=headers)
                    if audio_url and audio_url not in processed_urls:
                        clean_title = re.sub(r'[^a-z0-9-]', '', title.lower().replace(" ", "-"))[:50]
                        if download_file(audio_url, os.path.join(chroniques_dir, f"{clean_title}.mp3"), headers=headers):
                            processed_urls.add(audio_url)

    except Exception as e:
        print(f"   ❌ Erreur : {e}")

def main():
    if len(sys.argv) < 3: return
    start_date = datetime.strptime(sys.argv[1], "%d-%m-%Y")
    end_date = datetime.strptime(sys.argv[2], "%d-%m-%Y")
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5: process_date(curr.strftime("%d-%m-%Y"))
        curr += timedelta(days=1)

if __name__ == "__main__":
    main()
