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
        print(f"      ❌ Erreur : {e}")
        return False

def get_audio_url_from_page(page_url):
    """Récupère l'URL .mp3 sur la page individuelle."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        response = requests.get(page_url, timeout=10)
        if response.status_code != 200: return None
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.mp3", response.text)
        return match.group(0) if match else None
    except:
        return None

def find_audio_anywhere(id_or_uuid):
    """
    Cherche l'audio par tous les moyens possibles pour un identifiant donné.
    """
    # 1. Tentative via l'API manifestation directe (souvent utilisée pour le replay)
    # On teste avec l'UUID
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            url = data.get("url")
            if url and ".mp3" in url: return url, data.get("title")
    except: pass

    # 2. Tentative via l'API player (v1)
    try:
        api_url = f"https://www.radiofrance.fr/api/v1/player/manifestations/{id_or_uuid}"
        resp = requests.get(api_url, timeout=5)
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
    
    grid_url = f"https://www.radiofrance.fr/franceinfo/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10)
        if resp.status_code != 200: return
        
        # Identification du bloc 6/9
        match = re.search(r"\{[^}]*label:\"06h00\"[^}]*\}", resp.text)
        if not match: return
        show_id = re.search(r"id:\"([a-f0-9-]{36})\"", match.group(0)).group(1)
        
        dest_dir = f"../../../@assets/0.media/audio/3.franceinfo-matin/{target_date}"
        chroniques_dir = os.path.join(dest_dir, "chroniques")
        os.makedirs(chroniques_dir, exist_ok=True)

        # Appel API Chroniques
        build_hash = "1vzv7fl"
        payload_raw = [{"brand": 1, "parentStep": 2}, "franceinfo", show_id]
        payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
        api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

        api_resp = requests.get(api_url, timeout=10)
        if api_resp.status_code == 200:
            result_str = api_resp.json().get("result", "")
            
            # Extraction de TOUS les UUIDs et de TOUS les nombres longs (IDs ITEMA potentiels)
            uuids = list(set(re.findall(r'[a-f0-9-]{36}', result_str)))
            # Les liens de podcasts contiennent souvent l'ID numérique à la fin
            podcast_links = list(set(re.findall(r'/franceinfo/podcasts/[^"\\]+', result_str)))
            
            # On extrait aussi les IDs numériques isolés (souvent des manifestationIds)
            # On cherche des nombres de 7 ou 8 chiffres entourés de guillemets ou virgules
            potential_ids = list(set(re.findall(r'[:",](\d{7,8})[:",]', result_str)))
            
            all_targets = uuids + potential_ids
            print(f"   [*] {len(podcast_links)} podcasts et {len(all_targets)} IDs techniques identifiés.")
            
            processed_urls = set()

            # A. Podcasts d'abord
            for link in sorted(podcast_links):
                parts = link.split('/')
                show_name = parts[3] if len(parts) > 3 else "chronique"
                audio_url = get_audio_url_from_page(link)
                if audio_url:
                    dest_name = f"{target_date}.mp3" if show_name == "le-6-9" else f"{show_name}.mp3"
                    dest_path = os.path.join(dest_dir if show_name == "le-6-9" else chroniques_dir, dest_name)
                    if download_file(audio_url, dest_path):
                        processed_urls.add(audio_url)

            # B. Recherche exhaustive pour tout ce qui reste
            print(f"   [*] Recherche approfondie pour les segments manquants...")
            for target in sorted(all_targets):
                audio_url, title = find_audio_anywhere(target)
                if audio_url and audio_url not in processed_urls:
                    clean_title = re.sub(r'[^a-z0-9-]', '', title.lower().replace(" ", "-"))[:50]
                    dest_path = os.path.join(chroniques_dir, f"{clean_title}.mp3")
                    print(f"      📍 Trouvé via ID {target} : {title}")
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
