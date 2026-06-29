import mlx.core as mx
from huggingface_hub import hf_hub_download
import json

def check_mimi():
    repo = 'kyutai/stt-1b-en_fr-mlx'
    config_dict = json.load(open(hf_hub_download(repo, 'config.json')))
    mimi_path = hf_hub_download(repo, config_dict['mimi_name'])
    weights = mx.load(mimi_path)
    for k, v in weights.items():
        print(k, v.shape)

if __name__ == "__main__":
    check_mimi()
