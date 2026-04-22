import os
import re
import sys
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

def get_rss_feed(concept_url):
    """Récupère l'URL du flux RSS depuis la page d'une émission."""
    try:
        response = requests.get(concept_url, timeout=10)
        response.raise_for_status()
        match = re.search(r'rssFeed:"(https://[^"]*)"', response.text)
        return match.group(1) if match else None
    except:
        return None

def download_audio(url, filename):
    """Télécharge le fichier audio si celui-ci n'existe pas déjà."""
    if os.path.exists(filename):
        return
    
    print(f"  -> Téléchargement : {os.path.basename(filename)}")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except Exception as e:
        print(f"  ! Erreur sur {url}: {e}")

def process_date(date_str):
    """Télécharge les chroniques pour une date donnée (format DD-MM-YYYY)."""
    # Les deux flux principaux de la matinale (7/9 et Le Mag)
    concepts = [
        "https://www.radiofrance.fr/franceinter/podcasts/la-grande-matinale",
        "https://www.radiofrance.fr/franceinter/podcasts/la-grande-matinale-le-mag"
    ]

    os.makedirs(date_str, exist_ok=True)
    target_date = datetime.strptime(date_str, "%d-%m-%Y").date()
    
    episodes_found = 0
    for concept_url in concepts:
        rss_url = get_rss_feed(concept_url)
        if not rss_url: continue
            
        try:
            response = requests.get(rss_url, timeout=10)
            root = ET.fromstring(response.content)
            
            for item in root.findall('./channel/item'):
                pub_date_raw = item.find('pubDate').text
                # Format: Mon, 20 Apr 2026 09:49:40 +0200
                pub_dt = datetime.strptime(pub_date_raw[:-6], "%a, %d %b %Y %H:%M:%S")
                
                if pub_dt.date() == target_date:
                    title = item.find('title').text.strip()
                    enclosure = item.find('enclosure')
                    
                    if enclosure is not None:
                        # Filtrage : On ignore ce qui dure plus de 30 minutes (1800s)
                        # pour ne garder que les chroniques
                        duration = 0
                        itunes_dur = item.find('{http://www.itunes.com/dtds/podcast-1.0.dtd}duration')
                        if itunes_dur is not None:
                            try:
                                duration = int(itunes_dur.text)
                            except: pass
                        
                        # Si durée absente du XML, on se base sur la taille du fichier (estimée)
                        # ou on télécharge quand même si le titre ne contient pas "Le 7/9" ou "Le Mag"
                        is_full_show = "Le 7/9" in title or "Le Mag" in title or duration > 1800
                        
                        if not is_full_show:
                            audio_url = enclosure.get('url')
                            time_str = pub_dt.strftime("%Hh%M")
                            safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                            ext = "m4a" if ".m4a" in audio_url.lower() else "mp3"
                            
                            filename = os.path.join(date_str, f"[{time_str}] {safe_title}.{ext}")
                            download_audio(audio_url, filename)
                            episodes_found += 1
        except Exception as e:
            print(f"  ! Erreur flux RSS {concept_url}: {e}")
            
    print(f"--- Terminé pour le {date_str} : {episodes_found} chroniques récupérées ---")

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_franceinter_range.py DATE_DEBUT [DATE_FIN]")
        print("Format: DD-MM-YYYY (ex: 20-04-2026)")
        sys.exit(1)
    
    start_date = datetime.strptime(sys.argv[1], "%d-%m-%Y")
    end_date = datetime.strptime(sys.argv[2], "%d-%m-%Y") if len(sys.argv) > 2 else start_date
    
    curr = start_date
    while curr <= end_date:
        ds = curr.strftime("%d-%m-%Y")
        print(f"\nTraitement du {ds}...")
        process_date(ds)
        curr += timedelta(days=1)

if __name__ == "__main__":
    main()
