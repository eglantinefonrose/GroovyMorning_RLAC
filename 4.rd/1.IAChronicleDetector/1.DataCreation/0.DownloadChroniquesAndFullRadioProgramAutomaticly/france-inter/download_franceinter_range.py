import os
import re
import requests
import sys
import base64
import json
from datetime import datetime, timedelta

# Dossier de destination
BASE_DIR = "../../../../@assets/0.media/audio/4.franceinter-matin"

def download_file(url, dest_path, headers=None):
    """Télécharge un fichier si il n'existe pas déjà."""
    if os.path.exists(dest_path):
        print(f"      ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    
    # Création automatique des dossiers parents si nécessaire
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
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
    """Cherche l'audio par tous les moyens possibles pour un identifiant donné."""
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

def process_date(target_date):
    """Exécute la logique complète pour une date donnée."""
    print(f"\n[*] --- TRAITEMENT DU {target_date} (France Inter) ---")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'}
    
    # Dossier principal de la date
    date_dir = os.path.join(BASE_DIR, target_date)
    # Sous-dossier pour les chroniques
    chroniques_dir = os.path.join(date_dir, "chroniques")
    
    # Conversion de la date au format ISO pour l'API si besoin (ici DD-MM-YYYY pour la grille)
    grid_url = f"https://www.radiofrance.fr/franceinter/grille-programmes?date={target_date}"
    try:
        resp = requests.get(grid_url, timeout=10, headers=headers)
        if resp.status_code != 200: 
            print(f"   ⚠️ Grille indisponible pour le {target_date}")
            return
        content = resp.text

        # Build hash pour l'API
        build_hash_match = re.search(r"\"buildId\":\"([^\"]+)\"", content)
        build_hash = build_hash_match.group(1) if build_hash_match else "1vzv7fl"

        processed_shows = set()
        processed_urls = set()

        # Label à chercher dans la grille pour "Le 7/9"
        for label in ["07h00"]:
            # On cherche le bloc correspondant au label
            # Le format dans le HTML est souvent label="07h00" ou similaire dans les données JSON de Svelte
            match = re.search(rf'label:"{label}"[^}}]*id:"([a-f0-9-]{{36}})"', content)
            if not match:
                # Tentative alternative (format HTML attribut)
                match = re.search(rf'label="{label}"[^>]*data-element-id="([a-f0-9-]{{36}})"', content)
            
            if not match: continue
            
            show_id = match.group(1)
            if show_id in processed_shows: continue
            processed_shows.add(show_id)

            # Extraction du titre et du lien
            # On cherche le lien juste après le label
            link_match = re.search(rf'label[:=]"{label}".*?href[:=]"([^"]+)"[^>]*?>(.*?)</a>', content, re.DOTALL)
            if not link_match:
                # Tentative format JSON svelte
                link_match = re.search(rf'label:"{label}".*?href:"([^"]+)"', content, re.DOTALL)
            
            if not link_match: continue
            main_link = link_match.group(1)
            
            # Titre de l'émission
            show_title_match = re.search(rf'id:"{show_id}".*?title:"([^"]+)"', content)
            show_title = show_title_match.group(1) if show_title_match else "Emission"

            print(f"   [*] Segment trouvé : {show_title} ({label})")

            # 1. Téléchargement de l'intégrale à la RACINE du dossier date
            main_audio_url = get_audio_url_from_page(main_link, headers=headers)
            if main_audio_url:
                ext = "m4a" if ".m4a" in main_audio_url.lower() else "mp3"
                dest_name = f"[{label.replace('h', 'h')}] {re.sub(r'[^a-zA-Z0-9]', '_', show_title)}.{ext}"
                if download_file(main_audio_url, os.path.join(date_dir, dest_name), headers=headers):
                    processed_urls.add(main_audio_url)

            # 2. Appel API Chroniques
            # Payload pour loadChroniclesGrid : [{"brand": 1, "parentStep": 2}, "franceinter", show_id]
            payload_raw = [{"brand": 1, "parentStep": 2}, "franceinter", show_id]
            payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
            api_url = f"https://www.radiofrance.fr/_app/remote/{build_hash}/loadChroniclesGrid?payload={payload_b64}"

            api_resp = requests.get(api_url, headers=headers, timeout=10)
            if api_resp.status_code == 200:
                result_data = api_resp.json()
                # On cherche les liens de podcasts dans le résultat (qui est souvent du HTML ou du JSON)
                result_str = str(result_data.get("result", ""))
                
                # On extrait tous les liens vers /franceinter/podcasts/
                podcast_links = list(set(re.findall(r'/franceinter/podcasts/[^"\s\\]+', result_str)))
                
                for link in sorted(podcast_links):
                    # On ignore l'émission principale elle-même
                    if link == main_link or main_link in link: continue
                    
                    parts = link.split('/')
                    # parts[0]='', parts[1]='franceinter', parts[2]='podcasts', parts[3]='nom-chronique'
                    if len(parts) > 3:
                        show_name = parts[3]
                        # On récupère l'audio pour cette chronique
                        audio_url = get_audio_url_from_page(link, headers=headers)
                        if audio_url and audio_url not in processed_urls:
                            ext = "m4a" if ".m4a" in audio_url.lower() else "mp3"
                            # On télécharge dans le sous-dossier chroniques
                            # On essaie de trouver l'heure dans le titre ou le lien si possible, sinon pas grave
                            if download_file(audio_url, os.path.join(chroniques_dir, f"{show_name}.{ext}"), headers=headers):
                                processed_urls.add(audio_url)

    except Exception as e:
        print(f"   ❌ Erreur globale pour le {target_date} : {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_franceinter_range.py DATE_DEBUT [DATE_FIN]")
        print("Format: DD-MM-YYYY (ex: 20-04-2026)")
        sys.exit(1)
    
    start_date = datetime.strptime(sys.argv[1], "%d-%m-%Y")
    end_date = datetime.strptime(sys.argv[2], "%d-%m-%Y") if len(sys.argv) > 2 else start_date
    
    curr = start_date
    while curr <= end_date:
        # Lundi=0, Mardi=1, Mercredi=2, Jeudi=3.
        # Note: On garde la logique originale d'ignorer Vendredi-Dimanche si c'était voulu
        if curr.weekday() <= 3:
            ds = curr.strftime("%d-%m-%Y")
            process_date(ds)
        else:
            print(f"\nSaut du {curr.strftime('%d-%m-%Y')} (Vendredi-Dimanche)")
        curr += timedelta(days=1)

if __name__ == "__main__":
    main()
