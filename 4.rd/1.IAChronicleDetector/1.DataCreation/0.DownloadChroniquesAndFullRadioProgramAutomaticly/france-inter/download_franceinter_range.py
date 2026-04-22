import os
import re
import sys
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Dossier de destination mis à jour
BASE_DIR = "../../../../@assets/0.media/audio/4.franceinter-matin"

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
    
    # Création automatique des dossiers parents si nécessaire
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
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
    # Les flux de la matinale (Le 6/9, La grande matinale, Le Mag)
    concepts = [
        "https://www.radiofrance.fr/franceinter/podcasts/la-grande-matinale",
        "https://www.radiofrance.fr/franceinter/podcasts/la-grande-matinale-le-mag",
        "https://www.radiofrance.fr/franceinter/podcasts/le-6-7"
    ]

    # Dossier principal de la date
    date_dir = os.path.join(BASE_DIR, date_str)
    # Sous-dossier pour les chroniques
    chroniques_dir = os.path.join(date_dir, "chroniques")
    
    target_date = datetime.strptime(date_str, "%d-%m-%Y").date()
    
    files_found = 0
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
                    # On ne garde que ce qui est diffusé entre 6h et 10h pour le "6/9"
                    if not (6 <= pub_dt.hour < 10):
                        continue

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
                        
                        # Identification de l'émission complète
                        is_full_show = any(x in title for x in ["Le 7/9", "Le 6/9", "Le Mag", "Le 6/7"]) or duration > 1800
                        
                        audio_url = enclosure.get('url')
                        time_str = pub_dt.strftime("%Hh%M")
                        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
                        ext = "m4a" if ".m4a" in audio_url.lower() else "mp3"
                        
                        if is_full_show:
                            # À la racine du dossier de la date
                            filename = os.path.join(date_dir, f"[{time_str}] {safe_title}.{ext}")
                        else:
                            # Dans le sous-dossier chroniques
                            filename = os.path.join(chroniques_dir, f"[{time_str}] {safe_title}.{ext}")
                        
                        download_audio(audio_url, filename)
                        files_found += 1
        except Exception as e:
            print(f"  ! Erreur flux RSS {concept_url}: {e}")
            
    print(f"--- Terminé pour le {date_str} : {files_found} fichiers récupérés ---")

def main():
    if len(sys.argv) < 2:
        print("Usage: python download_franceinter_range.py DATE_DEBUT [DATE_FIN]")
        print("Format: DD-MM-YYYY (ex: 20-04-2026)")
        sys.exit(1)
    
    start_date = datetime.strptime(sys.argv[1], "%d-%m-%Y")
    end_date = datetime.strptime(sys.argv[2], "%d-%m-%Y") if len(sys.argv) > 2 else start_date
    
    curr = start_date
    while curr <= end_date:
        # Lundi=0, Mardi=1, Mercredi=2, Jeudi=3. On ignore Vendredi(4), Samedi(5), Dimanche(6).
        if curr.weekday() <= 3:
            ds = curr.strftime("%d-%m-%Y")
            print(f"\nTraitement du {ds}...")
            process_date(ds)
        else:
            print(f"\nSaut du {curr.strftime('%d-%m-%Y')} (Vendredi-Dimanche non demandés)")
        curr += timedelta(days=1)

if __name__ == "__main__":
    main()
