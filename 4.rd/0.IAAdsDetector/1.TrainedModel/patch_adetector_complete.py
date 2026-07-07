import os
import re

# Get the directory where the script is located
base_dir = os.path.dirname(os.path.abspath(__file__))
core_path = os.path.join(base_dir, "env/lib/python3.12/site-packages/adetector/core.py")

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
