import json
import os
import glob

# Configuration des chemins
TRANSCRIPT_FILE = "full_show_transcription.txt"
DETECTIONS_FILE = "detections_live.json"
GT_DIR = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/1.modelOutputs/0.transcriptions/2.transcriptions_kyutai_stt_2.6b_fr/4.franceinter-matin/27-05-2026/chroniques/start_transcription/"
OUTPUT_HTML = "viz.html"

def generate_viz():
    # 1. Lire la transcription
    if not os.path.exists(TRANSCRIPT_FILE):
        print(f"Erreur : {TRANSCRIPT_FILE} introuvable.")
        return
    with open(TRANSCRIPT_FILE, "r", encoding="utf-8") as f:
        transcript = f.read()

    # 2. Lire le Ground Truth
    gt_phrases = {}
    if os.path.exists(GT_DIR):
        for gt_file in glob.glob(os.path.join(GT_DIR, "*.txt")):
            chronique_name = os.path.basename(gt_file).replace("_start.txt", "")
            with open(gt_file, "r", encoding="utf-8") as f:
                phrase = f.read().strip()
                if phrase:
                    gt_phrases[phrase] = chronique_name
    else:
        print(f"Attention : Répertoire GT introuvable : {GT_DIR}")

    # 3. Lire l'Inférence
    inf_phrases = {}
    if os.path.exists(DETECTIONS_FILE):
        try:
            with open(DETECTIONS_FILE, "r", encoding="utf-8") as f:
                detections = json.load(f)
                for det in detections:
                    if isinstance(det, dict) and det.get("detecte"):
                        inf_phrases[det["phrase"]] = det["chronique"]
        except Exception as e:
            print(f"Erreur lecture inférence : {e}")

    # 4. Générer le HTML
    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Visualisation Chroniques</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; max-width: 1200px; margin: auto; padding: 20px; background: #f4f4f9; }}
        h1 {{ color: #333; }}
        .container {{ display: flex; gap: 20px; }}
        .text-view {{ flex: 3; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); white-space: pre-wrap; }}
        .legend {{ flex: 1; background: #fff; padding: 20px; border-radius: 8px; position: sticky; top: 20px; height: fit-content; }}
        .gt {{ background-color: #ffeb3b; border-bottom: 2px solid #fbc02d; font-weight: bold; cursor: help; }}
        .inf {{ background-color: #bbdefb; border-bottom: 2px solid #1976d2; font-weight: bold; cursor: help; }}
        .both {{ background-color: #c8e6c9; border-bottom: 2px solid #388e3c; font-weight: bold; cursor: help; }}
        .item {{ margin-bottom: 10px; padding: 5px; border-radius: 4px; }}
        hr {{ border: 0; border-top: 1px solid #eee; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Comparaison Ground Truth vs Inférence</h1>
    <div class="container">
        <div class="text-view" id="transcript">Chargement...</div>
        <div class="legend">
            <h3>Légende</h3>
            <div class="item gt">Jaune : Ground Truth (Réalité)</div>
            <div class="item inf">Bleu : Inférence (Détecté par Qwen)</div>
            <div class="item both">Vert : Les deux (Succès !)</div>
            <hr>
            <div id="stats"></div>
        </div>
    </div>

    <script>
        const fullText = {json.dumps(transcript, ensure_ascii=False)};
        const gtPhrases = {json.dumps(list(gt_phrases.keys()), ensure_ascii=False)};
        const infPhrases = {json.dumps(list(inf_phrases.keys()), ensure_ascii=False)};
        
        let highlighted = fullText;
        
        // On trie par longueur décroissante pour éviter que des petites phrases ne cassent des grandes
        const allPhrases = [...new Set([...gtPhrases, ...infPhrases])].sort((a, b) => b.length - a.length);

        allPhrases.forEach(phrase => {{
            const isGT = gtPhrases.includes(phrase);
            const isInf = infPhrases.includes(phrase);
            let className = "";
            if (isGT && isInf) className = "both";
            else if (isGT) className = "gt";
            else if (isInf) className = "inf";
            
            // Échapper la phrase pour le regex
            const escaped = phrase.replace(/[.*+?^${{}}()|[\]\\]/g, '\\\\$&');
            const regex = new RegExp(escaped, 'g');
            highlighted = highlighted.replace(regex, `<span class="${{className}}" title="${{phrase}}">${{phrase}}</span>`);
        }});

        document.getElementById('transcript').innerHTML = highlighted;
        document.getElementById('stats').innerHTML = `
            <p><strong>Ground Truth :</strong> ${{gtPhrases.length}}</p>
            <p><strong>Détectés par LLM :</strong> ${{infPhrases.length}}</p>
        `;
    </script>
</body>
</html>
"""
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Fichier généré : {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_viz()
