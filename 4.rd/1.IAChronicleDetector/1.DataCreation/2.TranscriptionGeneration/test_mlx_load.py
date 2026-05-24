import json
from huggingface_hub import hf_hub_download
import mlx.core as mx
import sentencepiece
import rustymimi
from moshi_mlx import models

def test_load():
    repo = "kyutai/stt-1b-en_fr-mlx"
    print(f"Loading config from {repo}")
    config_path = hf_hub_download(repo, "config.json")
    with open(config_path, "r") as f:
        config_dict = json.load(f)
    
    lm_config = models.LmConfig.from_config_dict(config_dict)
    model = models.Lm(lm_config)
    
    print("Loading model weights")
    model_path = hf_hub_download(repo, "model.safetensors")
    model.load_weights(model_path)
    
    print("Loading tokenizer")
    tokenizer_path = hf_hub_download(repo, config_dict["tokenizer_name"])
    tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
    
    print("Loading mimi weights")
    mimi_path = hf_hub_download(repo, config_dict["mimi_name"])
    mimi_tokenizer = rustymimi.Tokenizer(mimi_path, num_codebooks=lm_config.audio_codebooks)
    
    print("Success! Models loaded.")

if __name__ == "__main__":
    test_load()
