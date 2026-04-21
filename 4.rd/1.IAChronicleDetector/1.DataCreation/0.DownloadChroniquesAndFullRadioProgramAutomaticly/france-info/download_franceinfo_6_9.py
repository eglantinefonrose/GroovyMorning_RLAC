import os
import re
import requests
import sys
import base64
import json

def download_file(url, dest_path):
    if os.path.exists(dest_path):
        print(f"   ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    print(f"   📥 Téléchargement : {url}")
    try:
        if url.startswith('//'): url = 'https:' + url
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        print(f"   ✅ Sauvegardé.")
        return True
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False

def get_audio_url_from_page(page_url):
    """Récupère l'URL .mp3 sur la page individuelle d'une chronique."""
    try:
        if page_url.startswith('/'):
            page_url = f"https://www.radiofrance.fr{page_url}"
        
        response = requests.get(page_url, timeout=10)
        if response.status_code != 200: return None
        content = response.text
        # Recherche de l'URL du média
        match = re.search(r"https://media\.radiofrance-podcast\.net/[^\"]*\.mp3", content)
        return match.group(0) if match else None
    except: return None

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else "17-04-2026"
    print(f"[*] Traitement de France Info 'Le 6/9' pour le {target_date}...")

    # 1. Récupération des informations dans la grille
    grid_url = f"https://www.radiofrance.fr/franceinfo/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10)
        content = resp.text
        
        # Build hash par défaut
        build_hash = "1vzv7fl"
        
        # Recherche du bloc 06h00
        match = re.search(r"\{[^}]*label:\"06h00\"[^}]*\}", content)
        if not match:
            print("❌ Impossible de trouver le bloc 'Le 6/9' à 06h00 dans la grille.")
            return
        
        segment_data = match.group(0)
        
        # ID de l'expression (pour l'API)
        le_6_9_id_match = re.search(r"id:\"([a-f0-9-]{36})\"", segment_data)
        if not le_6_9_id_match:
            print("❌ ID de l'émission introuvable.")
            return
        le_6_9_id = le_6_9_id_match.group(1)
        print(f"[*] ID de l'émission trouvé : {le_6_9_id}")

        # Lien de l'intégrale
        main_link_match = re.search(r"href:\"(/franceinfo/podcasts/le-6-9/[^\"]*)\"", segment_data)
        main_link = main_link_match.group(1) if main_link_match else None
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse de la grille : {e}")
        return

    # Dossiers de destination
    dest_dir = f"../../../@assets/0.media/audio/3.franceinfo-matin/{target_date}"
    chroniques_dir = os.path.join(dest_dir, "chroniques")
    os.makedirs(chroniques_dir, exist_ok=True)

    # 2. Télécharger l'intégrale (un niveau au-dessus)
    if main_link:
        print(f"[*] Téléchargement de l'émission globale (Intégrale)...")
        main_audio_url = get_audio_url_from_page(main_link)
        if main_audio_url:
            download_file(main_audio_url, os.path.join(dest_dir, f"{target_date}.mp3"))
        else:
            print("   ⚠️ Impossible de trouver l'audio de l'intégrale.")
    else:
        print("   ⚠️ Lien de l'intégrale non trouvé dans le bloc.")

    # 3. Appel à l'API loadChroniclesGrid pour les chroniques
    payload_raw = [{"brand": 1, "parentStep": 2}, "franceinfo", le_6_9_id]
    payload_json = json.dumps(payload_raw, separators=(',', ':'))
    payload_b64 = base64.b64encode(payload_json.encode()).decode()
    
    api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

    print(f"[*] Récupération de la liste des chroniques via API...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Referer': grid_url,
            'x-sveltekit-pathname': '/franceinfo/grille-programmes'
        }
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Erreur API ({resp.status_code})")
            return
            
        data_outer = resp.json()
        result_str = data_outer.get("result", "")
        
        # Extraction des liens de podcasts
        links = re.findall(r"/franceinfo/podcasts/[^\"]+-[0-9]{7}", result_str)
        unique_links = sorted(list(set(links)))
        
        found_count = 0
        for link in unique_links:
            # On ignore le lien vers l'intégrale s'il est présent ici
            if "/le-6-9/" in link: continue
            
            show_name = link.split('/')[3]
            audio_url = get_audio_url_from_page(link)
            if audio_url:
                filename = f"{show_name}.mp3"
                if download_file(audio_url, os.path.join(chroniques_dir, filename)):
                    found_count += 1
                
        print(f"[*] Terminé. {found_count} chroniques téléchargées.")

    except Exception as e:
        print(f"❌ Erreur lors de l'appel API : {e}")

if __name__ == "__main__":
    main()
