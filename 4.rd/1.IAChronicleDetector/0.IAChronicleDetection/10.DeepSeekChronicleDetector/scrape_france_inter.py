import requests
import re
import json
import sys
import os
import base64
from datetime import datetime

# Configuration
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:151.0) Gecko/20100101 Firefox/151.0',
    'Accept': '*/*',
    'Content-Type': 'application/json',
}

def get_matinale_step_id(date_str=None):
    """
    Récupère dynamiquement l'ID du segment 'Matinale' pour une date donnée
    en interrogeant la grille des programmes via RPC.
    """
    # Date au format YYYY-MM-DD
    today = date_str if date_str else datetime.now().strftime("%Y-%m-%d")
    
    # Construction du payload pour loadProgramGrid
    # [["__skrao",1],{"brand":2,"date":3},"franceinter","YYYY-MM-DD"]
    payload_raw = [["__skrao", 1], {"brand": 2, "date": 3}, "franceinter", today]
    payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
    
    url_grid = f"https://www.radiofrance.fr/_app/remote/1vzv7fl/loadProgramGrid?payload={payload_b64}"
    
    try:
        response = requests.get(url_grid, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = json.loads(data.get('result', '[]'))
        
        # On cherche l'item qui correspond à la matinale (entre 6h et 9h ou 7h et 10h)
        # On cherche le UUID associé à "Le 6/9" ou "Le 7/10"
        for i, item in enumerate(items):
            if isinstance(item, str) and (item == "Le 6/9" or item == "Le 7/10"):
                # L'ID est souvent quelques indices avant ou après. 
                # Dans le format observé, l'ID (UUID) est à l'offset -2 ou -3 du titre du programme
                for offset in range(-10, 10):
                    idx = i + offset
                    if 0 <= idx < len(items):
                        val = items[idx]
                        if isinstance(val, str) and re.match(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', val):
                            return val
    except Exception as e:
        print(f"[SCRAPER] Erreur lors de la recherche de l'ID matinale : {e}")
    
    # Fallback
    return "4d701356-e8ea-40fc-b4e8-030bbd23ddce"

def fetch_chroniques_from_rpc(date_str=None):
    """Récupère et parse les chroniques via l'appel RPC complet."""
    step_id = get_matinale_step_id(date_str)
    
    # Payload : [["__skrao",1],{"brand":2,"parentStep":3},"franceinter","STEP_ID"]
    payload_raw = [["__skrao", 1], {"brand": 2, "parentStep": 3}, "franceinter", step_id]
    payload_b64 = base64.b64encode(json.dumps(payload_raw, separators=(',', ':')).encode()).decode()
    
    url_rpc = f'https://www.radiofrance.fr/_app/remote/1vzv7fl/loadChroniclesGrid?payload={payload_b64}'
    
    print(f"Appel API : {url_rpc}")
    
    try:
        response = requests.get(url_rpc, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = json.loads(data.get('result', '[]'))
    except Exception as e:
        print(f"[SCRAPER] Erreur RPC : {e}")
        return []

    if not items or not isinstance(items[0], list):
        return []

    start_indices = items[0]
    chroniques_ordered = []
    seen = set()
    keywords = ["journal", "édito", "billet", "chronique", "invité", "géopolitique", "mots nouveaux", "prouvé", "80 secondes", "oeil de", "un été avec", "la météo", "le grand entretien"]

    def normalize(text):
        t = text.lower()
        t = t.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("î", "i").replace("ï", "i")
        return t

    for start_idx in start_indices:
        # Heure
        time_str = "??h??"
        for offset in range(1, 15):
            idx = start_idx + offset
            if idx < len(items):
                val = items[idx]
                if isinstance(val, str) and re.match(r'\d{2}h\d{2}', val):
                    time_str = val
                    break
        
        # Titre
        block_title = ""
        # Priorité aux titres de titleProps
        for offset in range(1, 12):
            idx = start_idx + offset
            if idx < len(items):
                obj = items[idx]
                if isinstance(obj, dict) and 'title' in obj:
                    title_idx = obj['title']
                    if title_idx < len(items) and isinstance(items[title_idx], str):
                        block_title = items[title_idx]
                        break
        
        if not block_title:
            for offset in range(1, 20):
                idx = start_idx + offset
                if idx < len(items):
                    val = items[idx]
                    if isinstance(val, str) and len(val) > 3 and not val.startswith('/') and '©' not in val and not re.match(r'\d{2}h\d{2}', val):
                        if any(kw in normalize(val) for kw in keywords):
                            block_title = val
                            break

        if block_title:
            title_clean = block_title.strip()
            # Nettoyage journaux
            if "journal de 0" in title_clean.lower():
                title_clean = re.sub(r'[Ll]e journal de 0(\d)h[0-9]+.*', r'Le journal de \1h', title_clean)
            elif "journal de " in title_clean.lower():
                title_clean = re.sub(r'[Ll]e journal de (\d+)h[0-9]+.*', r'Le journal de \1h', title_clean)

            if title_clean not in seen:
                chroniques_ordered.append({"time": time_str, "title": title_clean})
                seen.add(title_clean)

    return chroniques_ordered

def get_chroniques(date_str=None):
    return fetch_chroniques_from_rpc(date_str)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date au format YYYY-MM-DD")
    args = parser.parse_args()
    
    chroniques = get_chroniques(args.date)
    if chroniques:
        print("\n" + "="*50)
        print(f" CHRONIQUES DU {args.date if args.date else 'JOUR'} (Ordre de passage)")
        print("="*50)
        for c in chroniques:
            print(f"{c['time']} | {c['title']}")
        print("="*50 + "\n")
    else:
        print("Aucune chronique récupérée.")
