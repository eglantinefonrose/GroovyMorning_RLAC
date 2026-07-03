"""
Détection de début de chroniques en flux simulé via Qwen (Ollama).
Adapté pour une machine avec 16 Go de RAM.
"""

import json
import re
import requests
import time
import sys

# Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:14b"

CHRONIQUES = [
    "les 80 secondes",
    "le grand reportage",
    "l'édito média",
    "musicaline",
    "l'édito politique",
    "l'édito éco",
    "l'invité de 7h50",
    "le billet de bertrand chameroy",
    "le journal de 8h",
    "geopolitique",
    "l'invité de 8h20",
    "dans l'oeil de",
    "un monde nouveau",
    "le billet de mosimann",
]

SYSTEM_PROMPT = f"""Tu es un expert radio chargé de détecter le début exact des chroniques.
Tu reçois un flux de phrases. Ta mission est de dire si la TOUTE DERNIÈRE phrase reçue marque le début d'une chronique.

Liste des chroniques à surveiller :
{json.dumps(CHRONIQUES, ensure_ascii=False)}

CONSIGNES :
1. Une annonce ("A 8h20, nous recevrons...") n'est PAS un début. 
2. Le début est quand l'animateur lance officiellement la chronique ("Il est 8h20, voici l'invité de...") ou quand le chroniqueur prend la parole.
3. Réponds uniquement en JSON.
4. Prends bien en compte l'ordre des chroniques.

EXEMPLES DE DÉBUTS RÉELS :
- "Et maintenant, 80 secondes de science en couleur..." -> {{"detecte": true, "chronique": "les 80 secondes", "phrase": "Et maintenant, 80 secondes de science en couleur..."}}
- "Benjamin Duhamel, vous recevez les auteurs d'une enquête sur le casse du Louvre." -> {{"detecte": true, "chronique": "l'invité de 7h50", "phrase": "Benjamin Duhamel, vous recevez les auteurs d'une enquête sur le casse du Louvre."}}
- "Bertrand Chameroy, deux des auteurs du livre sur les coulisses du Casse du Louvre, sont donc dans notre studio." -> {{"detecte": true, "chronique": "le billet de bertrand chameroy", "phrase": "Bertrand Chameroy, deux des auteurs du livre sur les coulisses du Casse du Louvre, sont donc dans notre studio."}}
- "Cyril Lacarrière, l'édito-média, désormais tous les matins, vous nous parlez aujourd'hui..." -> {{"detecte": true, "chronique": "l'édito média", "phrase": "Cyril Lacarrière, l'édito-média, désormais tous les matins, vous nous parlez aujourd'hui..."}}

EXEMPLES D'ANNONCES (À IGNORER) :
- "Qui recevez-vous à 7h50 ?" -> {{"detecte": false, "chronique": null, "phrase": null}}
- "À 8h20, Raphaël Glucksmann sera notre invité dans le grand entretien." -> {{"detecte": false, "chronique": null, "phrase": null}}

Format de réponse :
{{
  "detecte": true/false,
  "chronique": "Nom exact de la chronique ou null",
  "phrase": "La phrase exacte qui marque le début"
}}
"""

def split_sentences(text):
    """Découpage simple en phrases pour simuler un flux de transcription."""
    # Split sur . ! ? suivi d'un espace, tout en préservant l'heure (ex: 7h50)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def call_qwen_live(sentence, context_buffer):
    """Appelle le modèle pour analyser la phrase actuelle avec un peu de contexte."""
    context_text = "\n".join(context_buffer)
    user_content = f"CONTEXTE PRÉCÉDENT :\n{context_text}\n\nNOUVELLE PHRASE À ANALYSER :\n{sentence}"
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 100
        }
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if response.status_code == 404:
            return {"detecte": False, "error": "model_not_found"}
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "{}")
        return json.loads(content)
    except requests.exceptions.ConnectionError:
        print("\n[ERREUR] Impossible de se connecter à Ollama. Vérifiez qu'il est lancé.")
        sys.exit(1)
    except Exception:
        return {"detecte": False}

def simulate_audio_stream(file_path):
    """Lit le fichier et simule l'arrivée des phrases une par une."""
    print(f"Lecture du fichier : {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"Erreur : le fichier {file_path} est introuvable.")
        return []
    
    sentences = split_sentences(full_text)
    print(f"Simulation lancée : {len(sentences)} phrases à traiter.")
    print(f"Modèle utilisé : {MODEL}\n")
    
    context_buffer = []
    max_context = 2
    detections = []

    for i, current_sentence in enumerate(sentences):
        # Progression
        sys.stdout.write(f"\rTraitement phrase {i+1}/{len(sentences)}... ")
        sys.stdout.flush()
        
        result = call_qwen_live(current_sentence, context_buffer)
        
        if result.get("error") == "model_not_found":
            print(f"\n[ERREUR] Le modèle '{MODEL}' n'est pas installé sur Ollama.")
            print(f"Lancez : ollama pull {MODEL}")
            sys.exit(1)

        if result.get("detecte"):
            chronique = result.get("chronique")
            phrase = result.get("phrase")
            print(f"\n\n[DÉTECTION] 🔔 Chronique trouvée : {chronique}")
            print(f"Phrase : \"{phrase}\"")
            print("-" * 50)
            detections.append(result)
            
        context_buffer.append(current_sentence)
        if len(context_buffer) > max_context:
            context_buffer.pop(0)
            
    print(f"\nFin de la simulation. {len(detections)} chroniques détectées.")
    return detections

if __name__ == "__main__":
    TRANSCRIPTION_FILE = "full_show_transcription.txt"
    all_detections = simulate_audio_stream(TRANSCRIPTION_FILE)
    
    if all_detections:
        with open("detections_live.json", "w", encoding="utf-8") as f:
            json.dump(all_detections, f, ensure_ascii=False, indent=2)
