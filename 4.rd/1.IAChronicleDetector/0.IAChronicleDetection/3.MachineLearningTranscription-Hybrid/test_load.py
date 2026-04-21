from utils import load_transcription
import os

srt_content = """1
00:00:01,000 --> 00:00:04,000
Bonjour à tous.

2
00:00:05,000 --> 00:00:08,000
Bienvenue sur notre antenne.
"""

with open("test.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

segments = load_transcription("test.srt")
print(f"Segments chargés: {len(segments)}")
for s in segments:
    print(f"Segment {s['index']}: [{s['start']}-{s['end']}] -> '{s['text']}'")

os.remove("test.srt")
