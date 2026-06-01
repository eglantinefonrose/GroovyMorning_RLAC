import json
import mlx.core as mx
from huggingface_hub import hf_hub_download
from moshi_mlx import models

REPO = "kyutai/stt-1b-en_fr-mlx"

config_path = hf_hub_download(REPO, "config.json")
with open(config_path, "r") as f:
    config_dict = json.load(f)
    
print("Config dict max_seq_len:", config_dict.get("max_seq_len"))
print("Config dict context:", config_dict.get("context"))

lm_config = models.LmConfig.from_config_dict(config_dict)
print("LM Config transformer max_seq_len:", lm_config.transformer.max_seq_len)
print("LM Config transformer context:", lm_config.transformer.context)
