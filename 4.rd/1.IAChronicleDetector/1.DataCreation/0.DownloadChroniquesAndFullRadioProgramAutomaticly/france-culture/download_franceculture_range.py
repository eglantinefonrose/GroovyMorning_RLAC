import os
import re
import requests
import sys
import base64
import json
from datetime import datetime, timedelta

def download_file(url, dest_path):
    """Télécharge un fichier si il n'existe pas déjà."""
    if os.path.exists(dest_path):
        print(f"      ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    
    print(f"      📥 Téléchargement : {url}")
    try:
        if url.startswith('//'): url = 'https:' + url
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"      ✅ Sauvegardé.")
        return True
    except Exception as e:
        print(f"      ❌ Erreur réseau lors du téléchargement : {e}")
        return False

def get_audio_url_from_page(page_url):
    """Récupère l'URL .mp3 sur la page individuelle d'un podcast."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0'}
        response = requests.get(page_url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.mp3", response.text)
        return match.group(0) if match else None
    except:
        return None

def get_audio_url_simple(player_id):
    """Récupère l'URL audio via l'API de manifestation (pour les orphelins)."""
    url = f"https://www.radiofrance.fr/api/v1/player/manifestations?uuids={player_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0',
        'Accept': 'application/json'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            manifest = data.get(player_id)
            if manifest:
                title = manifest.get("title", "segment")
                sources = manifest.get("sources", [])
                for s in sources:
                    if s.get("url") and ".mp3" in s["url"]:
                        return s["url"], title
        return None, None
    except:
        return None, None

def process_date(target_date):
    """Exécute la logique complète pour une date donnée."""
    print(f"\n[*] --- TRAITEMENT DU {target_date} (France Culture) ---")
    
    grid_url = f"https://www.radiofrance.fr/franceculture/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10)
        if resp.status_code != 200: 
            print(f"   ⚠️ Grille indisponible.")
            return
        
        # 1. Identification du bloc "Les Matins" (07h00)
        match = re.search(r"\{[^}]*label:\"07h00\"[^}]*\}", resp.text)
        if not match:
            match = re.search(r"\{[^}]*title:\"Les Matins\"[^}]*\}", resp.text)
        if not match:
            print("   ⚠️ Émission 'Les Matins' non trouvée.")
            return
        
        block_data = match.group(0)
        show_id = re.search(r"id:\"([a-f0-9-]{36})\"", block_data).group(1)
        href_match = re.search(r"href:\"([^\"]+)\"", block_data)
        main_link = href_match.group(1) if href_match else None
        
        dest_dir = f"../../../@assets/0.media/audio/4.franceculture-matin/{target_date}"
        chroniques_dir = os.path.join(dest_dir, "chroniques")
        os.makedirs(chroniques_dir, exist_ok=True)

        processed_urls = set()

        # 2. TÉLÉCHARGEMENT DE L'INTÉGRALE
        print(f"   [+] Téléchargement de l'intégrale...")
        integral_url = None
        # Option A : Via le lien de la page
        if main_link:
            integral_url = get_audio_url_from_page(main_link)
        # Option B : Via l'UUID si l'option A échoue
        if not integral_url:
            integral_url, _ = get_audio_url_simple(show_id)
        
        if integral_url:
            if download_file(integral_url, os.path.join(dest_dir, f"{target_date}.mp3")):
                processed_urls.add(integral_url)
        else:
            print(f"      ⚠️ Impossible de trouver l'URL audio de l'intégrale.")

        # 3. APPEL API DES CHRONIQUES
        build_hash = "1vzv7fl"
        payload_raw = [{"brand": 1, "parentStep": 2}, "franceculture", show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

        api_resp = requests.get(api_url, timeout=10)
        if api_resp.status_code == 200:
            result_str = api_resp.json().get("result", "")
            
            # Liens de podcasts
            podcast_links = sorted(list(set(re.findall(r'/franceculture/podcasts/[^"\\]+', result_str))))
            print(f"   [+] Analyse de {len(podcast_links)} liens de podcasts...")
            for link in podcast_links:
                parts = link.split('/')
                show_name = parts[3] if len(parts) > 3 else "chronique"
                
                audio_url = get_audio_url_from_page(link)
                if audio_url:
                    if audio_url in processed_urls: continue
                    dest_path = os.path.join(chroniques_dir, f"{show_name}.mp3")
                    if download_file(audio_url, dest_path):
                        processed_urls.add(audio_url)
                else:
                    print(f"      ⚠️ Aucun audio MP3 trouvé sur la page : {link}")

            # UUIDs restants (orphelins)
            uuids = sorted(list(set(re.findall(r'[a-f0-9-]{36}', result_str))))
            print(f"   [+] Analyse de {len(uuids)} segments UUIDs pour les orphelins...")
            for uid in uuids:
                if uid == show_id: continue
                audio_url, title = get_audio_url_simple(uid)
                if audio_url and audio_url not in processed_urls:
                    clean_title = re.sub(r'[^a-z0-9-]', '', title.lower().replace(" ", "-"))[:50]
                    dest_path = os.path.join(chroniques_dir, f"{clean_title}.mp3")
                    if download_file(audio_url, dest_path):
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
