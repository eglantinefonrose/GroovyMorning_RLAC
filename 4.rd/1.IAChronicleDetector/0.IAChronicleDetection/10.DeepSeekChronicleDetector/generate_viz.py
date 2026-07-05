import json
import os

# Configuration des chemins
TRANSCRIPT_FILE = "full_show_transcription.txt"
DETECTIONS_FILE = "detections_output/detections_live_deepseek.json"
OUTPUT_HTML = "viz.html"

def generate_viz():
    # 1. Lire la transcription
    if not os.path.exists(TRANSCRIPT_FILE):
        print(f"Erreur : {TRANSCRIPT_FILE} introuvable.")
        return
    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        transcript = f.read()

    # 2. Lire l'Inférence Claude
    inf_phrases = {}
    if os.path.exists(DETECTIONS_FILE):
        try:
            with open(DETECTIONS_FILE, "r", encoding="utf-8") as f:
                detections = json.load(f)
                for item in detections:
                    det = item.get("result", {})
                    if det.get("detecte"):
                        inf_phrases[det["phrase"]] = det["chronique"]
        except Exception as e:
            print(f"Erreur lecture inférence : {e}")
    else:
        print(f"Attention : Fichier de détection introuvable : {DETECTIONS_FILE}")

    # 3. Générer le HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Visualisation Chroniques - Claude</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; max-width: 1200px; margin: auto; padding: 20px; background: #f4f4f9; }}
        h1 {{ color: #333; }}
        .container {{ display: flex; gap: 20px; }}
        .text-view {{ flex: 3; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); white-space: pre-wrap; }}
        .legend {{ flex: 1; background: #fff; padding: 20px; border-radius: 8px; position: sticky; top: 20px; height: fit-content; }}
        .inf {{ background-color: #bbdefb; border-bottom: 2px solid #1976d2; font-weight: bold; cursor: help; }}
        .item {{ margin-bottom: 10px; padding: 5px; border-radius: 4px; }}
        hr {{ border: 0; border-top: 1px solid #eee; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Détection de Chroniques via Claude 3.5 Sonnet</h1>
    <div class="container">
        <div class="text-view" id="transcript">Chargement...</div>
        <div class="legend">
            <h3>Légende</h3>
            <div class="item inf">Bleu : Détecté par Claude</div>
            <hr>
            <div id="stats"></div>
            <hr>
            <h4>Chroniques détectées :</h4>
            <ul id="chronicle-list"></ul>
        </div>
    </div>

    <script>
        const fullText = {json.dumps(transcript, ensure_ascii=False)};
        const infPhrases = {json.dumps(inf_phrases, ensure_ascii=False)};
        
        let highlighted = fullText;
        
        // On trie par longueur décroissante
        const phrasesToHighlight = Object.keys(inf_phrases).sort((a, b) => b.length - a.length);

        phrasesToHighlight.forEach(phrase => {{
            const chronique = inf_phrases[phrase];
            // Échapper la phrase pour le regex
            const escaped = phrase.replace(/[.*+?^${{}}()|[\]\\]/g, '\\\\$&');
            const regex = new RegExp(escaped, 'g');
            highlighted = highlighted.replace(regex, `<span class="inf" title="Chronique : ${{chronique}}">${{phrase}}</span>`);
        }});

        document.getElementById('transcript').innerHTML = highlighted;
        document.getElementById('stats').innerHTML = `
            <p><strong>Chroniques détectées :</strong> ${{Object.keys(inf_phrases).length}}</p>
        `;
        
        const list = document.getElementById('chronicle-list');
        Object.entries(inf_phrases).forEach(([phrase, chronique]) => {{
            const li = document.createElement('li');
            li.innerHTML = `<strong>${{chronique}}</strong><br><small style="color: #666;">${{phrase}}</small>`;
            li.style.marginBottom = "10px";
            list.appendChild(li);
        }});
    </script>
</body>
</html>
"""
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Fichier généré : {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_viz()
