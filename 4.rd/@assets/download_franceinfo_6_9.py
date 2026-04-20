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

    # 1. Récupération de l'ID de l'émission dans la grille
    grid_url = f"https://www.radiofrance.fr/franceinfo/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10)
        content = resp.text
        
        # Extraction du hash de build (ex: 1vzv7fl)
        build_hash_match = re.search(r"/_app/immutable/assets/_page\.client\.([^.]+)\.js", content)
        if not build_hash_match:
            # Fallback sur une autre méthode si le hash n'est pas là
            build_hash = "1vzv7fl"
        else:
            # Note: Le hash dans loadChroniclesGrid n'est pas forcément le même que les JS. 
            # On utilise le vôtre par défaut s'il marche bien.
            build_hash = "1vzv7fl"

        # Recherche du bloc 06h00 pour trouver l'UUID
        match = re.search(r"\{[^}]*label:\"06h00\"[^}]*\}", content)
        if not match:
            print("❌ Impossible de trouver l'ID du 6/9 dans la grille.")
            return
        
        le_6_9_id = re.search(r"id:\"([a-f0-9-]{36})\"", match.group(0)).group(1)
        print(f"[*] ID de l'émission trouvé : {le_6_9_id}")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse de la grille : {e}")
        return

    # 2. Appel à l'API loadChroniclesGrid
    payload_raw = [{"brand": 1, "parentStep": 2}, "franceinfo", le_6_9_id]
    payload_json = json.dumps(payload_raw, separators=(',', ':'))
    payload_b64 = base64.b64encode(payload_json.encode()).decode()
    
    api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"
    
    dest_dir = f"0.media/audio/3.franceinfo-matin/{target_date}"
    chroniques_dir = os.path.join(dest_dir, "chroniques")
    os.makedirs(chroniques_dir, exist_ok=True)

    print(f"[*] Récupération de la liste des chroniques...")
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
        
        # On extrait tous les liens de podcasts du résultat sérialisé
        # Format : /franceinfo/podcasts/NOM-CHRONIQUE/TITRE-ID
        links = re.findall(r"/franceinfo/podcasts/[^\"]+-[0-9]{7}", result_str)
        
        unique_links = sorted(list(set(links)))
        print(f"[*] {len(unique_links)} chroniques identifiées.")

        found_count = 0
        for link in unique_links:
            # On ignore le lien vers l'intégrale s'il est présent
            if "/le-6-9/" in link: continue
            
            # Nom propre du programme (ex: le-briefing-politique)
            show_name = link.split('/')[3]
            
            audio_url = get_audio_url_from_page(link)
            if audio_url:
                filename = f"{show_name}.mp3"
                if download_file(audio_url, os.path.join(chroniques_dir, filename)):
                    found_count += 1
                
        print(f"[*] Terminé. {found_count} fichiers téléchargés dans {chroniques_dir}")

    except Exception as e:
        print(f"❌ Erreur lors de l'appel API : {e}")

if __name__ == "__main__":
    main()
