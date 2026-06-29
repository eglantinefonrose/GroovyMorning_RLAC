import rustymimi
import numpy as np
import mlx.core as mx
from huggingface_hub import hf_hub_download
import json

REPO = "kyutai/stt-1b-en_fr-mlx"
config_path = hf_hub_download(REPO, "config.json")
config_dict = json.load(open(config_path))
mimi_path = hf_hub_download(REPO, config_dict["mimi_name"])

tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=32)
pcm = np.zeros((1, 1, 1920), dtype=np.float32)
tokens = tokenizer.encode_step(pcm)
print("Tokens type:", type(tokens))
print("Tokens shape:", tokens.shape)

tokens_mx = mx.array(tokens)
print("Tokens MX shape:", tokens_mx.shape)
other_codebooks = 32
other_audio_tokens_mx = tokens_mx.transpose(0, 2, 1)[:, :, :other_codebooks]
print("Other audio tokens MX shape:", other_audio_tokens_mx.shape)
print("Other audio tokens MX [0] shape:", other_audio_tokens_mx[0].shape)
