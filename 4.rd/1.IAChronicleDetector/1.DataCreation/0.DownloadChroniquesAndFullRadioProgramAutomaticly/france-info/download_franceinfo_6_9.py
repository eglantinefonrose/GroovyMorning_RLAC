import os
import re
import requests
import sys
import base64
import json

def download_file(url, dest_path, headers=None):
    if os.path.exists(dest_path):
        print(f"   ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    print(f"   📥 Téléchargement : {url}")
    try:
        if url.startswith('//'): url = 'https:' + url
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        print(f"   ✅ Sauvegardé.")
        return True
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False

def get_audio_url_from_page(page_url, headers=None):
    """Récupère l'URL .mp3 sur la page individuelle d'une chronique."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        
        response = requests.get(page_url, timeout=10, headers=headers)
        if response.status_code != 200: return None
        content = response.text
        # Recherche de l'URL du média
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.mp3", content)
        return match.group(0) if match else None
    except: return None

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else "17-04-2026"
    print(f"[*] Traitement de France Info pour le {target_date}...")

    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'}

    # Dossiers de destination
    dest_dir = f"../../../@assets/0.media/audio/3.franceinfo-matin/{target_date}"
    chroniques_dir = os.path.join(dest_dir, "chroniques")
    os.makedirs(chroniques_dir, exist_ok=True)

    # 1. Récupération des informations dans la grille
    grid_url = f"https://www.radiofrance.fr/franceinfo/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, headers=headers, timeout=10)
        content = resp.text
        
        # Build hash
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"
        
        processed_shows = set()

        for label in ["06h00"]:
            # Nouvelle structure HTML: label="06h00" et data-element-id="UUID"
            match = re.search(rf'label="{label}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
            if not match: continue
            
            show_id = match.group(1)
            
            # Recherche du lien href associé
            link_match = re.search(rf'label="{label}".*?<a href="([^"]+)"[^>]*data-testid="Link"[^>]*>(.*?)</a>', content, re.DOTALL)
            if not link_match: continue
            
            main_link, show_title = link_match.groups()
            show_title = re.sub('<[^>]*>', '', show_title).strip()
            
            if show_id in processed_shows: continue
            processed_shows.add(show_id)

            print(f"[*] Traitement de : {show_title} ({label})")

            # Téléchargement de l'intégrale
            print(f"   [*] Téléchargement de l'intégrale...")
            main_audio_url = get_audio_url_from_page(main_link, headers=headers)
            if main_audio_url:
                dest_name = f"{target_date}.mp3" if "06h00" in label else f"{re.sub(r'[^a-z0-9]', '-', show_title.lower())}.mp3"
                download_file(main_audio_url, os.path.join(dest_dir, dest_name), headers=headers)
            else:
                print("      ⚠️ Audio de l'intégrale non trouvé.")

            # Récupération des chroniques
            payload_raw = [{"brand": 1, "parentStep": 2}, "franceinfo", show_id]
            payload_json = json.dumps(payload_raw, separators=(',', ':'))
            payload_b64 = base64.b64encode(payload_json.encode()).decode()
            
            api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

            try:
                api_resp = requests.get(api_url, headers=headers, timeout=10)
                if api_resp.status_code == 200:
                    data_outer = api_resp.json()
                    result_str = data_outer.get("result", "")
                    links = re.findall(r"/franceinfo/podcasts/[^\"]+-[0-9]{7}", result_str)
                    unique_links = sorted(list(set(links)))
                    
                    for link in unique_links:
                        if link in main_link: continue
                        show_name = link.split('/')[3]
                        audio_url = get_audio_url_from_page(link, headers=headers)
                        if audio_url:
                            filename = f"{show_name}.mp3"
                            download_file(audio_url, os.path.join(chroniques_dir, filename), headers=headers)
            except Exception as e:
                print(f"      ❌ Erreur API chroniques : {e}")

    except Exception as e:
        print(f"❌ Erreur : {e}")

    print(f"[*] Terminé pour le {target_date}.")

if __name__ == "__main__":
    main()
