import mlx.core as mx
from moshi_mlx import models, utils
import json
from huggingface_hub import hf_hub_download

def test_offset():
    repo = "kyutai/stt-1b-en_fr-mlx"
    config_dict = json.load(open(hf_hub_download(repo, "config.json")))
    lm_config = models.LmConfig.from_config_dict(config_dict)
    model = models.Lm(lm_config)
    
    steps = 10000
    chunk_size_steps = 3000
    overlap_steps = 125
    
    for start_step in range(0, steps, chunk_size_steps - overlap_steps):
        end_step = min(start_step + chunk_size_steps, steps)
        print(f"Chunk {start_step} to {end_step}")
        
        for c in model.transformer_cache:
            c.reset()
            
        from moshi_mlx.models import LmGen
        gen = LmGen(
            model=model,
            max_steps=(end_step - start_step) + 10,
            text_sampler=utils.Sampler(temp=0.0),
            audio_sampler=utils.Sampler(temp=0.0),
            check=False,
        )
        
        other_audio_tokens_mx = mx.zeros((1, 1, 32))
        
        for rel_idx in range(end_step - start_step):
            text_token, _ = gen.step(other_audio_tokens_mx[0])
            text_token.item()
            
            # Check offset of first layer cache
            offset = model.transformer_cache[0].self_attn.offset
            if offset >= 8192:
                print(f"ERROR: Offset reached {offset} at step {start_step + rel_idx}")
                return
        
        print(f"End of chunk, offset was {model.transformer_cache[0].self_attn.offset}")

if __name__ == "__main__":
    test_offset()
