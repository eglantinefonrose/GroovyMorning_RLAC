from utils import load_transcription
import os

srt_content = """[00:00:00.200 --> 00:00:01.180]   France Inter.
[00:00:01.180 --> 00:00:03.460]   France Inter, je confirme, il est 7 heures.
"""

with open("test_user_format.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

segments = load_transcription("test_user_format.srt")
print(f"Segments chargés: {len(segments)}")
for s in segments:
    print(f"Segment {s['index']}: [{s['start']}-{s['end']}] -> '{s['text']}'")

os.remove("test_user_format.srt")
