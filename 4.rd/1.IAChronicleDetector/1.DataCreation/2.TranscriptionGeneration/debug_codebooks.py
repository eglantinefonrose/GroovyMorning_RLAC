import json
from huggingface_hub import hf_hub_download
from moshi_mlx import models

REPO = "kyutai/stt-1b-en_fr-mlx"

config_path = hf_hub_download(REPO, "config.json")
with open(config_path, "r") as f:
    config_dict = json.load(f)
    
lm_config = models.LmConfig.from_config_dict(config_dict)
print("Audio codebooks:", lm_config.audio_codebooks)
print("Generated codebooks:", lm_config.generated_codebooks)
print("Other codebooks:", lm_config.other_codebooks)
print("Depformer slices:", lm_config.depformer.num_slices if lm_config.depformer else 0)
