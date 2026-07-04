import re

def extract():
    try:
        with open("episode_2026-05-27.html", "r") as f:
            html = f.read()
        
        # On extrait TOUTES les chaînes entre guillemets
        strings = re.findall(r'"((?:[^"\\]|\\.)*)"', html)
        print(f"Total strings found: {len(strings)}")
        
        # On cherche des titres probables
        seen = set()
        for s in strings:
            s = s.replace('\\"', '"').strip()
            if len(s) > 8 and not any(kw in s.lower() for kw in ["svelte", "image", "visual", "label", "item", "expandable", "dominant", "color", "http", "rules", "handle"]):
                if not re.match(r'[0-9a-f]{8}-', s.lower()):
                    if s not in seen:
                        # On affiche tout ce qui ressemble à un titre
                        if any(kw in s.lower() for kw in ["journal", "édito", "billet", "chronique", "géopolitique", "météo", "invité", "entretien", "80 secondes", "oeil de", "un été avec"]):
                            print(f"TITLE FOUND: {s}")
                            seen.add(s)
                            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract()
