import re
import os
import sys
from datetime import datetime

def parse_srt(file_path):
    segments = []
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Format: [00:00:00.000 --> 00:00:01.200]   [JINGLE] France Inter
    pattern = re.compile(r'\[(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)')
    
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            segments.append({
                'start': match.group(1),
                'end': match.group(2),
                'text': match.group(3).strip()
            })
    return segments

def get_day_of_week(filename):
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', filename)
    if match:
        day, month, year = map(int, match.groups())
        dt = datetime(year, month, day)
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return days[dt.weekday()]
    return None

def analyze_file(file_path):
    filename = os.path.basename(file_path)
    day = get_day_of_week(filename)
    segments = parse_srt(file_path)
    
    planning = [
        {"time": "00:00:00", "name": "Le journal de 7h", "keywords": ["journal", "Victor Dolan", "7h"], "default_host": "Victor Dolan"},
        {"time": "00:13:00", "name": "Les 80''", "keywords": ["80''", "80 secondes", "Simon Lesbarou"], "default_host": "Simon Lesbarou"},
        {"time": "00:16:00", "name": "Le Grand reportage de France Inter", "keywords": ["grand reportage", "Agathe Mahuel"], "default_host": "Agathe Mahuel"},
        {"time": "00:20:00", "name": "L'édito médias", "keywords": ["édito médias", "Cyril Lacarrière"], "default_host": "Cyril Lacarrière"},
        {"time": "00:23:00", "name": "Musicaline", "keywords": ["Musicaline", "Aline Afanoukoué", "Musique Aline"], "default_host": "Aline Afanoukoué"},
        {"time": "00:28:00", "name": "La météo", "keywords": ["météo", "Marie-Pierre Planchon"], "default_host": "Marie-Pierre Planchon"},
        {"time": "00:30:00", "name": "Le journal de 7h30", "keywords": ["journal", "7h30", "trente", "Victor Dolan", "Laurence Thomas"], "default_host": "Victor Dolan"},
        {"time": "00:43:00", "name": "L'édito politique", "keywords": ["édito politique", "politique"], "default_host": ""},
        {"time": "00:46:00", "name": "L'édito éco", "keywords": ["édito éco", "éco", "économie"], "default_host": ""},
        {"time": "00:49:00", "name": "L'invité de 7h50", "keywords": ["7h50", "invité", "cinquante"], "default_host": ""},
        {"time": "00:56:00", "name": "Le billet de Bertrand Chameroy", "keywords": ["Chameroy", "billet"], "default_host": "Bertrand Chameroy"},
        {"time": "01:00:00", "name": "Le journal de 8h", "keywords": ["journal", "8h", "huit heures"], "default_host": "Victor Dolan"},
        {"time": "01:17:00", "name": "Géopolitique", "keywords": ["Géopolitique", "Pierre Haski"], "default_host": "Pierre Haski"},
        {"time": "01:21:00", "name": "L'invité de 8h20", "keywords": ["8h20", "vingt", "grand entretien"], "default_host": ""},
        {"time": "01:46:00", "name": "Dans l'œil de", "keywords": ["œil", "Philippe Collin"], "default_host": "Philippe Collin"},
        {"time": "01:52:00", "name": "Un monde nouveau", "keywords": ["monde nouveau", "Mathilde Serrell"], "default_host": "Mathilde Serrell"},
    ]
    
    if day == "Lundi":
        planning.append({"time": "01:54:00", "name": "Merci Véro", "keywords": ["Merci Véro", "Véro", "Catherine Meurisse", "Loïc Prigent"], "default_host": "Catherine Meurisse / Loïc Prigent"})
    elif day == "Mardi":
        planning.append({"time": "01:54:00", "name": "Dans la bouche de Sofia Aram", "keywords": ["Sofia Aram", "bouche"], "default_host": "Sofia Aram"})
    elif day == "Mercredi":
        planning.append({"time": "01:54:00", "name": "Le billet de Mosimann", "keywords": ["Mosimann", "billet"], "default_host": "Mosimann"})
    elif day == "Jeudi":
        planning.append({"time": "01:54:00", "name": "La question de David Castello-Lopes", "keywords": ["David Castello-Lopes", "question"], "default_host": "David Castello-Lopes"})

    results = []
    
    for p in planning:
        target_time = p['time']
        target_seconds = sum(x * int(t) for x, t in zip([3600, 60, 1], target_time.split(':')))
        
        min_diff = 1200 # Increased to 20 minutes for flexibility
        found_start = None
        found_host = p['default_host']
        
        # Wider search range because of observed shifts
        search_range_start = max(0, target_seconds - 600) 
        search_range_end = target_seconds + 900
        
        for s in segments:
            s_start_sec = sum(x * float(t) for x, t in zip([3600, 60, 1], s['start'].split(':')))
            if search_range_start <= s_start_sec <= search_range_end:
                for kw in p['keywords']:
                    if kw.lower() in s['text'].lower():
                        diff = abs(s_start_sec - target_seconds)
                        if diff < min_diff:
                            min_diff = diff
                            found_start = s['start']
                            # Host refinement logic
                            hosts = ["Victor Dolan", "Simon Lesbarou", "Agathe Mahuel", "Cyril Lacarrière", "Aline Afanoukoué", 
                                     "Marie-Pierre Planchon", "Bertrand Chameroy", "Pierre Haski", "Philippe Collin", 
                                     "Mathilde Serrell", "Sofia Aram", "Mosimann", "David Castello-Lopes", "Catherine Meurisse", 
                                     "Loïc Prigent", "Laurence Thomas", "Léonie Simaga"]
                            for host in hosts:
                                if host.lower() in s['text'].lower():
                                    found_host = host
        
        if found_start:
            results.append({
                "name": p['name'],
                "host": found_host,
                "start": found_start
            })
    
    # Sort by start time then by name to keep them consistent
    results.sort(key=lambda x: (x['start'], x['name']))
    
    # Deduplicate if exact same start and name
    unique_results = []
    seen = set()
    for r in results:
        key = (r['start'], r['name'])
        if key not in seen:
            unique_results.append(r)
            seen.add(key)
    
    final_output = []
    for i in range(len(unique_results)):
        start = unique_results[i]['start']
        if i + 1 < len(unique_results):
            end = unique_results[i+1]['start']
        else:
            if segments:
                end = segments[-1]['end']
            else:
                end = start
        
        final_output.append(f"[{start}] - [{end}] {unique_results[i]['name']} - {unique_results[i]['host']}")
    
    return final_output

def main():
    dir_path = '0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo'
    output_dir = '1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/1.round2'
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    files = [f for f in os.listdir(dir_path) if f.endswith('.srt')]
    
    for filename in files:
        file_path = os.path.join(dir_path, filename)
        print(f"Analyzing {filename}...")
        results = analyze_file(file_path)
        
        output_filename = filename.replace('.srt', '_chronique.txt')
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
        print(f"Saved to {output_filename}")

if __name__ == '__main__':
    main()
