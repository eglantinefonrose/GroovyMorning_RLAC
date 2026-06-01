import mlx.core as mx
from huggingface_hub import hf_hub_download

REPO = "kyutai/stt-1b-en_fr-mlx"
try:
    path = hf_hub_download(REPO, "model.safetensors")
    weights = mx.load(path)
    for k, v in weights.items():
        if any(s == 8192 for s in v.shape):
            print(k, v.shape)
except Exception as e:
    print(f"Error: {e}")
