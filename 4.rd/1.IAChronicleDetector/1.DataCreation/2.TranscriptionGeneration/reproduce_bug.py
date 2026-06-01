import mlx.core as mx
import mlx.nn as nn
from moshi_mlx import models, utils
import json
from huggingface_hub import hf_hub_download

def reproduce():
    repo = "kyutai/stt-1b-en_fr-mlx"
    config_path = hf_hub_download(repo, "config.json")
    with open(config_path, "r") as f:
        config_dict = json.load(f)
    
    lm_config = models.LmConfig.from_config_dict(config_dict)
    model = models.Lm(lm_config)
    
    # We don't even need to load weights for this test
    # We just want to see if the loop fails
    
    from moshi_mlx.models import LmGen
    max_steps = 9000
    gen = LmGen(
        model=model,
        max_steps=max_steps,
        text_sampler=utils.Sampler(temp=0.0),
        audio_sampler=utils.Sampler(temp=0.0),
        check=False,
        cfg_coef=2.0,
    )
    
    other_audio_tokens_mx = mx.zeros((1, 1, 32))
    
    print("Starting loop...")
    for i in range(8500):
        if i % 1000 == 0:
            print(f"Step {i}")
        text_token, _ = gen.step(other_audio_tokens_mx[0])
        # Force evaluation
        text_token.item()
    print("Done!")

if __name__ == "__main__":
    reproduce()
