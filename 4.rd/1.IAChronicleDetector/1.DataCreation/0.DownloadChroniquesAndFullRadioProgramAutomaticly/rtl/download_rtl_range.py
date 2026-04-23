import os
import re
import requests
import sys
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# Configuration des flux
FEEDS = [
    ("b799ffaa-ccee-4a9a-a75f-0137a5787288", "laurent-gerra"),
    ("bd84bb2f-2f24-44a5-87ec-4851ba856c6a", "l-invite-de-rtl"),
    ("01a5bd92-d6c8-4572-8092-88e4c9953cc9", "l-oeil-de-philippe-caveriviere"),
    ("aeb105e8-907f-4710-b9d9-54ba21ca6e8c", "rtl-matin"),
]

# Namespace pour iTunes
NS = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}

def download_file(url, dest_path):
    """Télécharge un fichier si il n'existe pas déjà."""
    if os.path.exists(dest_path):
        print(f"      ✅ Déjà présent : {os.path.basename(dest_path)}")
        return True
    
    print(f"      📥 Téléchargement : {url}")
    try:
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

def slugify(text):
    """Transforme un texte en slug."""
    text = text.lower()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9]', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text

def get_chronique_slug(item, feed_slug):
    """Détermine le nom général de la chronique (slug)."""
    title = item.find('title').text
    title_upper = title.upper()
    
    # 1. Ignorer les bonus, pépites, archives et best-of
    ignore_keywords = ["PÉPITE", "10 ANS", "BONUS", "BEST OF", "MEILLEUR DE", "PODCAST"]
    if any(k in title_upper for k in ignore_keywords):
        return None

    # 2. Si c'est l'intégrale du flux général
    if feed_slug == "rtl-matin" and ("INTÉGRALE" in title_upper or re.match(r"RTL Matin du \d+", title)):
        return "integrale"

    # 3. Identification par mots-clés (Heuristiques) - Priorité haute
    heuristics = [
        (r"Laurent Gerra", "laurent-gerra"),
        (r"L'œil de Philippe Caverivière", "l-oeil-de-philippe-caveriviere"),
        (r"L'œil d'Alex Vizorek", "l-oeil-d-alex-vizorek"),
        (r"Le Cave' réveil", "le-cave-reveil"),
        (r"L'invité de RTL", "l-invite-de-rtl"),
        (r"L'angle éco", "l-angle-eco"),
        (r"Lenglet", "l-angle-eco"),
        (r"L'édito politique", "l-edito-politique"),
        (r"Le billet de Cyprien Cini", "le-billet-de-cyprien-cini"),
        (r"Amandine Bégot", "amandine-begot"),
    ]
    for pattern, slug in heuristics:
        if re.search(pattern, title, re.IGNORECASE):
            return slug

    # 4. Identification par auteur
    author_tag = item.find('itunes:author', NS)
    if author_tag is not None and author_tag.text:
        author = author_tag.text.strip()
        if author and author.upper() != "RTL":
            author_map = {
                "Caverivière": "l-oeil-de-philippe-caveriviere",
                "Vizorek": "l-oeil-d-alex-vizorek",
                "Lenglet": "l-angle-eco",
                "Gerra": "laurent-gerra",
                "Cini": "le-billet-de-cyprien-cini",
                "Ventura": "l-edito-politique",
                "Bégot": "amandine-begot"
            }
            for key, slug in author_map.items():
                if key in author: return slug

    # 5. Si on est dans un flux spécialisé (ex: flux Laurent Gerra), 
    # on utilise le nom du flux par défaut pour tout ce qui n'a pas été ignoré.
    if feed_slug != "rtl-matin":
        return feed_slug

    # 6. Pour le flux général (rtl-matin), si on n'a rien trouvé, on ignore.
    # On ne veut pas créer de fichiers basés sur le titre variable du jour.
    return None

def extract_audio_id(url):
    """Extrait l'ID unique de l'URL Audiomeans."""
    match = re.search(r"-([a-f0-9]{8,})\.mp3", url)
    if match: return match.group(1)
    return url

def process_date_range(start_date, end_date):
    """Parcourt les flux et télécharge les épisodes."""
    processed_ids = set()
    
    for feed_id, feed_slug in FEEDS:
        print(f"\n[*] --- TRAITEMENT DU FLUX : {feed_slug} ---")
        feed_url = f"https://feeds.audiomeans.fr/feed/{feed_id}.xml"
        
        try:
            resp = requests.get(feed_url, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            
            items = root.findall('.//item')
            print(f"   [+] {len(items)} épisodes trouvés.")

            for item in items:
                title = item.find('title').text
                pub_date_str = item.find('pubDate').text
                
                try:
                    dt = datetime.strptime(pub_date_str[:16], "%a, %d %b %Y")
                except: continue

                if start_date <= dt <= end_date:
                    date_str = dt.strftime("%d-%m-%Y")
                    
                    enclosure = item.find('enclosure')
                    if enclosure is None: continue
                    audio_url = enclosure.get('url')
                    
                    audio_id = extract_audio_id(audio_url)
                    if (date_str, audio_id) in processed_ids:
                        continue
                    
                    slug = get_chronique_slug(item, feed_slug)
                    if not slug:
                        continue
                    
                    dest_dir = f"../../../../@assets/0.media/audio/5.rtl-matin/{date_str}"
                    chroniques_dir = os.path.join(dest_dir, "chroniques")
                    os.makedirs(chroniques_dir, exist_ok=True)
                    
                    if slug == "integrale":
                        dest_path = os.path.join(dest_dir, f"{date_str}.mp3")
                    else:
                        dest_path = os.path.join(chroniques_dir, f"{slug}.mp3")
                    
                    if download_file(audio_url, dest_path):
                        processed_ids.add((date_str, audio_id))

        except Exception as e:
            print(f"   ❌ Erreur sur le flux {feed_slug} : {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 download_rtl_range.py <start_date> <end_date>")
        return

    try:
        start_date = datetime.strptime(sys.argv[1], "%d-%m-%Y")
        end_date = datetime.strptime(sys.argv[2], "%d-%m-%Y")
    except ValueError:
        print("❌ Format de date invalide. Utilisez JJ-MM-AAAA.")
        return

    process_date_range(start_date, end_date)

if __name__ == "__main__":
    main()
