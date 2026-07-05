import re

def dump():
    try:
        with open("debug_grille.html", "r") as f:
            html = f.read()
        
        # On cherche toutes les heures
        times = re.findall(r'(\d{2}h\d{2})', html)
        print(f"Total times found: {len(times)}")
        
        for t in sorted(set(times)):
            hour = int(t.split('h')[0])
            if 6 <= hour <= 9:
                print(f"\n--- {t} ---")
                pos = html.find(t)
                # On extrait les chaînes aux alentours
                window = html[pos:pos+3000]
                strings = re.findall(r'"([^"\\{}]{3,100})"', window)
                for s in strings:
                    if not any(kw in s.lower() for kw in ["svelte", "image", "visual", "label", "item", "expandable", "dominant", "color"]):
                        if not re.match(r'[0-9a-f]{8}-', s.lower()):
                            print(f"  {s}")
                            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump()
