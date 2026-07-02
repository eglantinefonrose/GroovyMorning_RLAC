"""
Détection de début de chroniques en flux simulé via Claude (Anthropic).
"""

import os
import json
import re
import time
import sys
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# On utilise le modèle corrigé : claude-sonnet-5
MODEL = "claude-opus-4-8"

if not ANTHROPIC_API_KEY:
    print("[ERREUR] La variable d'environnement ANTHROPIC_API_KEY n'est pas définie.")
    sys.exit(1)

# Plus besoin du client SDK Anthropic, on va utiliser requests (curl-like)

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

Liste des chroniques à surveiller (dans l'ordre) :
{json.dumps(CHRONIQUES, ensure_ascii=False)}

DÉFINITIONS CRUCIALES :
- ANNONCE / TEASING (À IGNORER) : L'animateur annonce ce qui va arriver PLUS TARD ("Tout à l'heure à 8h20...", "On en parlera avec notre invité après le journal..."). Le futur est utilisé.
- LANCEMENT RÉEL (À DÉTECTER) : C'est le moment précis où la chronique commence MAINTENANT. L'animateur donne la parole au chroniqueur ou présente l'invité présent.

EXEMPLES DE RÉFÉRENCE :

1. ANNONCE (À IGNORER) :
Phrase : "À 8h20, Raphaël Glucksmann sera notre invité dans le grand entretien."
JSON : {{
  "raisonnement": "C'est une annonce pour un segment futur (8h20).",
  "detecte": false,
  "chronique": null,
  "phrase": null
}}

2. LANCEMENT RÉEL (À DÉTECTER) :
Phrase : "Il est 8h20, l'invité de 8h20, Benjamin Duhamel vous recevez Raphaël Glucksmann."
JSON : {{
  "raisonnement": "Lancement immédiat, l'heure coïncide et l'invité est introduit.",
  "detecte": true,
  "chronique": "l'invité de 8h20",
  "phrase": "Il est 8h20, l'invité de 8h20, Benjamin Duhamel vous recevez Raphaël Glucksmann."
}}

3. ANNONCE RÉPÉTÉE (À IGNORER) :
Phrase : "À suivre, bien réveillé d'ici 7h30, Cyril, la carrière et Alina Fanouko est bonjour !"
JSON : {{
  "raisonnement": "Simple rappel d'un programme à venir ('tout à l'heure').",
  "detecte": false,
  "chronique": null,
  "phrase": null
}}

4. LANCEMENT CHRONIQUE (À DÉTECTER) :
Phrase : "Voici l'édito média, Cyril Lacarrière, ce matin, vous nous parlez d'un petit nouveau dans les médias français."
JSON : {{
  "raisonnement": "Lancement direct de la chronique avec salutation du chroniqueur.",
  "detecte": true,
  "chronique": "l'édito média",
  "phrase": "Cyril Lacarrière, l'édito-média, c'est tous les matins à 7h40, bonjour Cyril."
}}

CONSIGNES :
1. Analyse le contexte précédent (5 phrases) pour détecter les indicateurs temporels.
2. Réponds UNIQUEMENT en JSON.

Format de réponse attendu :
{{
  "raisonnement": "Analyse brève",
  "detecte": true/false,
  "chronique": "Nom exact ou null",
  "phrase": "La phrase exacte ou null"
}}
"""

def split_sentences(text):
    """Découpage simple en phrases pour simuler un flux de transcription."""
    # Split sur . ! ? suivi d'un espace, tout en préservant l'heure (ex: 7h50)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def call_claude_live(sentence, context_buffer):
    """Appelle l'API Anthropic via requests (équivalent curl)."""
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    context_text = "\n".join(context_buffer)
    user_content = f"CONTEXTE PRÉCÉDENT :\n{context_text}\n\nNOUVELLE PHRASE À ANALYSER :\n{sentence}"
    
    data = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_content}
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            print(f"\n[ERREUR API] Status {response.status_code}: {response.text}")
            return {"detecte": False}
            
        result = response.json()
        
        # Vérification robuste de la structure de réponse
        if "content" not in result or not isinstance(result["content"], list) or len(result["content"]) == 0:
            print(f"\n[ERREUR API] Structure de réponse inattendue : {json.dumps(result, indent=2)}")
            return {"detecte": False}
            
        # Chercher le premier bloc de type "text"
        content = ""
        for block in result["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                content = block.get("text", "").strip()
                break
            elif isinstance(block, dict):
                print(f"\n[INFO] Bloc de type non-textuel ignoré : {block.get('type')}")
        
        if not content:
            print(f"\n[ERREUR API] Aucun contenu textuel trouvé dans la réponse.")
            print(f"RÉPONSE COMPLÈTE : {json.dumps(result, indent=2)}")
            return {"detecte": False}
        
        # Nettoyage des balises markdown si présentes (ex: ```json ... ```)
        clean_content = content
        if clean_content.startswith("```"):
            # Enlever la première ligne (```json) et la dernière (```)
            lines = clean_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_content = "\n".join(lines).strip()

        # Tentative d'extraction du JSON par regex
        json_match = re.search(r'\{.*\}', clean_content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                # Si c'est tronqué, on essaie de fermer le JSON manuellement pour le debug
                # mais le mieux est d'augmenter max_tokens
                pass
        
        try:
            return json.loads(clean_content)
        except json.JSONDecodeError:
            print(f"\n[ERREUR] La réponse n'est pas un JSON valide.")
            if result.get("stop_reason") == "max_tokens":
                print("⚠️ RAISON : La réponse a été TRONQUÉE (max_tokens trop bas).")
            print(f"CONTENU REÇU : {content}")
            return {"detecte": False}
            
    except Exception as e:
        print(f"\n[ERREUR imprévue] {type(e).__name__}: {e}")
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
    max_context = 5
    detections = []

    # Pour éviter de trop consommer de tokens/argent pendant les tests, 
    # on pourrait limiter le nombre de phrases. Mais ici on suit la demande.
    # Note: Dans un vrai usage, on ferait du batching ou on optimiserait.

    for i, current_sentence in enumerate(sentences):
        # Progression
        sys.stdout.write(f"\rTraitement phrase {i+1}/{len(sentences)}... ")
        sys.stdout.flush()
        
        result = call_claude_live(current_sentence, context_buffer)
        
        if result.get("detecte"):
            chronique = result.get("chronique")
            phrase = result.get("phrase")
            print(f"\n\n[DÉTECTION] 🔔 Chronique trouvée : {chronique}")
            print(f"Phrase : \"{phrase}\"")
            print("-" * 50)
            detections.append({
                "index": i,
                "result": result
            })
            
        context_buffer.append(current_sentence)
        if len(context_buffer) > max_context:
            context_buffer.pop(0)
            
    print(f"\nFin de la simulation. {len(detections)} chroniques détectées.")
    return detections

if __name__ == "__main__":
    TRANSCRIPTION_FILE = "full_show_transcription.txt"
    all_detections = simulate_audio_stream(TRANSCRIPTION_FILE)
    
    if all_detections:
        with open("detections_live_claude.json", "w", encoding="utf-8") as f:
            json.dump(all_detections, f, ensure_ascii=False, indent=2)
