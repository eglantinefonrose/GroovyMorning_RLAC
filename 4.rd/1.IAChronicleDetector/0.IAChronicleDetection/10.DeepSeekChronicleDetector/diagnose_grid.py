import re
import json

def diagnose():
    try:
        with open("debug_grille.html", "r") as f:
            html = f.read()
        blocks = re.findall(r'\["([^"]*loadProgramGrid/[^"]*)","(.*?)"\]', html)
        print(f"Blocks found: {len(blocks)}")
        
        for i, (key, value) in enumerate(blocks):
            print(f"\n--- Block {i} ---")
            cleaned = value.replace('\\"', '"').replace('\\\\', '\\')
            try:
                data = json.loads(cleaned)
                times_and_titles = []
                current_time = None
                
                for s in data:
                    if isinstance(s, str):
                        if re.match(r'\d{2}h\d{2}', s):
                            current_time = s
                        elif current_time and len(s) > 5 and not s.startswith('/') and not s.isdigit():
                            if not re.match(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', s.lower()):
                                if not any(kw in s.lower() for kw in ["visual", "label", "item", "expandable", "image"]):
                                    times_and_titles.append((current_time, s))
                
                times_and_titles.sort()
                for t, title in times_and_titles:
                    print(f"{t} | {title}")
            except Exception as e:
                print(f"Error parsing block {i}: {e}")
    except Exception as e:
        print(f"General error: {e}")

if __name__ == "__main__":
    diagnose()
