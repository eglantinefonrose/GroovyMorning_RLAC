import os
import json
import subprocess
import sys
import numpy as np
from pathlib import Path

class Transcriber:
    def __init__(self, model_size="base", device=None, compute_type="int8", provider="whisper"):
        """
        Initialise le modèle de transcription.
        provider: "whisper", "kyutai" (Rust binary), "kyutai_mlx" (Mac native), or "kyutai_stt" (Transformers)
        """
        self.provider = provider
        self.model_size = model_size
        
        # Détection automatique du device
        if device is None:
            if sys.platform == "darwin":
                device = "mps"
            elif provider == "whisper" and compute_type == "int8":
                device = "cpu" # faster-whisper default for int8
            else:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = device

        if provider == "whisper":
            from faster_whisper import WhisperModel
            print(f"[WHISPER] Chargement du modèle '{model_size}' sur {device} ({compute_type})...")
            # whisper needs 'cpu' if no cuda
            whisper_device = "cpu" if device not in ["cuda"] else device
            self.model = WhisperModel(model_size, device=whisper_device, compute_type=compute_type)
        elif provider == "kyutai":
            print(f"[KYUTAI] Initialisation du transcripteur Kyutai STT (Rust)...")
            self.binary_path = self._find_kyutai_binary()
        elif provider == "kyutai_mlx":
            print(f"[KYUTAI_MLX] Initialisation du transcripteur Kyutai STT (MLX)...")
            self._init_kyutai_mlx()
        elif provider == "kyutai_stt":
            print(f"[KYUTAI_STT] Initialisation du modèle kyutai/stt-1b-en_fr (Transformers)...")
            self._init_kyutai_stt()

    def _init_kyutai_stt(self):
        try:
            import torch
            from transformers import KyutaiSpeechToTextProcessor, KyutaiSpeechToTextForConditionalGeneration
            
            model_id = "kyutai/stt-1b-en_fr-trfs"
            print(f"[KYUTAI_STT] Chargement du modèle {model_id} sur {self.device}...")
            
            self.processor = KyutaiSpeechToTextProcessor.from_pretrained(model_id)
            self.model = KyutaiSpeechToTextForConditionalGeneration.from_pretrained(
                model_id, 
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
            ).to(self.device)
            print("[KYUTAI_STT] Initialisation réussie.")
        except Exception as e:
            print(f"[KYUTAI_STT] Erreur d'initialisation : {e}")
            raise

    def _init_kyutai_mlx(self):
        try:
            import mlx.core as mx
            import mlx.nn as nn
            import sentencepiece
            import rustymimi
            from huggingface_hub import hf_hub_download
            from moshi_mlx import models, utils

            # Repository MLX standard pour Moshiko (Q8)
            repo_id = "kyutai/moshiko-mlx-q8"
            
            # Utilise la config par défaut de moshi_mlx pour le modèle Lm
            self.lm_config = models.config_v0_1()
            self.model = models.Lm(self.lm_config)
            self.model.set_dtype(mx.bfloat16)
            
            # Quantification en 8-bit (doit correspondre au repo q8)
            nn.quantize(self.model, bits=8, group_size=64)
            
            # Téléchargement manuel des poids car config.json peut manquer
            print(f"[KYUTAI_MLX] Téléchargement des poids depuis {repo_id}...")
            moshi_weights = hf_hub_download(repo_id, "model.q8.safetensors")
            self.model.load_weights(moshi_weights, strict=True)
            
            tokenizer_path = hf_hub_download(repo_id, "tokenizer_spm_32k_3.model")
            self.text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
            
            mimi_weights = hf_hub_download(repo_id, "tokenizer-e351c8d8-checkpoint125.safetensors")
            # Moshiko utilise 8 codebooks pour Mimi
            self.audio_tokenizer = rustymimi.Tokenizer(mimi_weights, num_codebooks=8)
            
            self.model.warmup()
            self.utils = utils
            self.mx = mx
            print("[KYUTAI_MLX] Initialisation réussie.")
        except Exception as e:
            print(f"[KYUTAI_MLX] Erreur d'initialisation : {e}")
            raise

    def _find_kyutai_binary(self):
        # Chemins potentiels pour le binaire
        paths = [
            Path(__file__).resolve().parent.parent.parent / "1.DataCreation/7.kyutai-VADDetection/delayed-streams-modeling/stt-rs/target/release/kyutai-stt-rs",
            Path("/usr/local/bin/kyutai-stt-rs"),
            Path("./kyutai-stt-rs")
        ]
        for p in paths:
            if p.exists():
                return str(p)
        return "kyutai-stt-rs" # Espérer qu'il soit dans le PATH

    def transcribe_stream(self, audio_path, language="fr"):
        """
        Générateur qui transcrit le fichier audio et renvoie les segments.
        """
        if self.provider == "whisper":
            print(f"[WHISPER] Début de la transcription ({language}) : {audio_path}")
            segments, info = self.model.transcribe(audio_path, beam_size=5, language=language)
            for segment in segments:
                yield {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                }
        elif self.provider == "kyutai":
            yield from self._transcribe_kyutai(audio_path)
        elif self.provider == "kyutai_mlx":
            yield from self._transcribe_kyutai_mlx(audio_path)
        elif self.provider == "kyutai_stt":
            yield from self._transcribe_kyutai_stt(audio_path)

    def _transcribe_kyutai_stt(self, audio_path):
        """Transcription via Transformers (stt-1b-en_fr)."""
        import torch
        import librosa
        print(f"[KYUTAI_STT] Début de la transcription : {audio_path}")
        
        # Audio must be 24kHz
        audio, _ = librosa.load(audio_path, sr=24000)
        
        # Chunk processing to simulate stream if it's a long file
        chunk_size = 24000 * 30 # 30 seconds chunks
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            if len(chunk) == 0:
                continue
            
            # Utilisation explicite de audio= pour garantir que le processeur capture les données
            inputs = self.processor(audio=chunk, sampling_rate=24000, return_tensors="pt").to(self.device)
            
            # Extraction de la clé input_values qui est vitale pour Kyutai STT
            input_values = inputs.get("input_values")
            if input_values is None:
                # Fallback sur input_features si nécessaire
                input_values = inputs.get("input_features")
            
            if input_values is None:
                print(f"[ERREUR] Le processeur n'a pas généré de données audio (Clés: {list(inputs.keys())})")
                continue

            gen_kwargs = {
                "input_values": input_values,
                "max_new_tokens": 128, # Limite pour éviter les boucles infinies sur de petits chunks
            }
            
            # Ajout du masque de padding s'il existe
            mask = inputs.get("attention_mask") or inputs.get("padding_mask")
            if mask is not None:
                gen_kwargs["attention_mask"] = mask

            with torch.no_grad():
                output_tokens = self.model.generate(**gen_kwargs)
            
            transcription = self.processor.batch_decode(output_tokens, skip_special_tokens=True)[0]
            
            if transcription.strip():
                yield {
                    "start": i / 24000,
                    "end": min((i + chunk_size) / 24000, len(audio) / 24000),
                    "text": transcription.strip()
                }

    def _transcribe_kyutai_mlx(self, audio_path):
        import sphn
        from moshi_mlx import models
        print(f"[KYUTAI_MLX] Début de la transcription : {audio_path}")
        
        # Audio must be 24kHz mono
        in_pcms, _ = sphn.read(audio_path, sample_rate=24000)
        
        # Padding
        pad_right = int(1.5 * 24000)
        in_pcms = np.pad(in_pcms, pad_width=[(0, 0), (0, pad_right)], mode="constant")
        
        steps = np.shape(in_pcms)[-1] // 1920
        gen = models.LmGen(
            model=self.model,
            max_steps=steps,
            text_sampler=self.utils.Sampler(top_k=25, temp=0.8),
            audio_sampler=self.utils.Sampler(top_k=250, temp=0.8),
            cfg_coef=1.0,
            check=False,
        )

        current_segment = {"text": "", "start": 0.0, "end": 0.0}
        
        for idx in range(steps):
            pcm_data = in_pcms[:, idx * 1920:(idx + 1) * 1920]
            other_audio_tokens = self.audio_tokenizer.encode_step(pcm_data[None, 0:1])
            other_audio_tokens = self.mx.array(other_audio_tokens).transpose(0, 2, 1)[:, :, :self.lm_config.other_codebooks]
            
            text_token = gen.step(other_audio_tokens[0], None)
            text_token = text_token[0].item()
            
            if text_token not in (0, 3):
                piece = self.text_tokenizer.id_to_piece(text_token).replace("▁", " ")
                if current_segment["text"] == "":
                    current_segment["start"] = idx * (1920 / 24000)
                
                current_segment["text"] += piece
                current_segment["end"] = (idx + 1) * (1920 / 24000)
                
                if piece.strip() and piece.strip()[-1] in ".!?":
                    yield {
                        "start": current_segment["start"],
                        "end": current_segment["end"],
                        "text": current_segment["text"].strip()
                    }
                    current_segment = {"text": "", "start": current_segment["end"], "end": current_segment["end"]}
        
        if current_segment["text"].strip():
            yield {
                "start": current_segment["start"],
                "end": current_segment["end"],
                "text": current_segment["text"].strip()
            }

    def _transcribe_kyutai(self, audio_path):
        """
        Lance le binaire Kyutai et parse la sortie en temps réel.
        """
        # Support pour stdin via '-' ou '/dev/stdin'
        input_path = audio_path
        if input_path == "-":
            input_path = "/dev/stdin"
            
        print(f"[KYUTAI] Début de la transcription : {input_path}")
        cmd = [self.binary_path, input_path, "--timestamps", "--vad", "--cpu"]
        
        try:
            # Si on lit depuis stdin, on s'assure que le processus enfant peut lire le stdin du parent
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                stdin=sys.stdin if input_path == "/dev/stdin" else None,
                text=True
            )
            
            current_segment = {"text": "", "start": None, "end": None}
            SILENCE_THRESHOLD = 0.8
            
            for line in process.stdout:
                line = line.strip()
                if not line: continue
                
                try:
                    data = json.loads(line)
                    word = data.get("word") or data.get("text")
                    if word is None: continue
                    
                    start = data.get("start")
                    end = data.get("end")
                    
                    if current_segment["start"] is None:
                        current_segment["start"] = start
                        current_segment["text"] = word
                    elif start - current_segment["end"] > SILENCE_THRESHOLD:
                        yield current_segment
                        current_segment = {"text": word, "start": start, "end": end}
                    else:
                        current_segment["text"] += " " + word
                    
                    current_segment["end"] = end
                    
                    if word.strip()[-1] in ".!?":
                        yield current_segment
                        current_segment = {"text": "", "start": None, "end": None}
                        
                except json.JSONDecodeError:
                    continue
            
            if current_segment["text"]:
                yield current_segment
                
            process.wait()
        except Exception as e:
            print(f"[KYUTAI] Erreur : {e}")
