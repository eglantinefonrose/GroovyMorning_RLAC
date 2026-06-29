import os
import re

core_path = "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.r&d/0.IAAdsDetector/1.TrainedModel/env/lib/python3.12/site-packages/adetector/core.py"

with open(core_path, 'r') as f:
    content = f.read()

# Correction 1: mfcc parameter
content = re.sub(
    r'librosa\.feature\.mfcc\(clip,\s*sr=sr,',
    'librosa.feature.mfcc(y=clip, sr=sr,',
    content
)

# Correction 2: timestamps.shape[0] -> len(timestamps)
content = re.sub(
    r'timestamps\.shape\[0\]',
    'len(timestamps)',
    content
)

with open(core_path, 'w') as f:
    f.write(content)

print("✅ Toutes les corrections ont été appliquées !")
