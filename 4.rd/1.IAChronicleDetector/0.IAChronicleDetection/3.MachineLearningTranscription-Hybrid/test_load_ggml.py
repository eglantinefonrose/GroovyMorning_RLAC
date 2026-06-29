from utils import load_transcription
import os

srt_content = """[00:00:00.000 --> 00:00:05.000]   Bonjour.
[00:00:05.000 --> 00:00:10.000]   Comment allez-vous ?
"""

with open("test_ggml.srt", "w", encoding="utf-8") as f:
    f.write(srt_content)

segments = load_transcription("test_ggml.srt")
print(f"Segments chargés: {len(segments)}")
for s in segments:
    print(f"Segment {s['index']}: [{s['start']}-{s['end']}] -> '{s['text']}'")

os.remove("test_ggml.srt")
