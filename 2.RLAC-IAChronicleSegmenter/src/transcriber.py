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
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
        
        self.device = device

        if provider == "whisper":
            try:
                from faster_whisper import WhisperModel
                print(f"[WHISPER] Chargement du modèle '{model_size}' sur {device} ({compute_type})...")
                # whisper needs 'cpu' if no cuda
                whisper_device = "cpu" if device not in ["cuda"] else device
                self.model = WhisperModel(model_size, device=whisper_device, compute_type=compute_type)
            except ImportError:
                import whisper
                print(f"[WHISPER] Chargement du modèle standard '{model_size}' sur {device}...")
                self.model = whisper.load_model(model_size, device=device)
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
            Path(__file__).resolve().parent.parent.parent.parent / "1.DataCreation/7.kyutai-VADDetection/delayed-streams-modeling/stt-rs/target/release/kyutai-stt-rs",
            Path("/usr/local/bin/kyutai-stt-rs"),
            Path("./kyutai-stt-rs")
        ]
        for p in paths:
            if p.exists():
                return str(p)
        return "kyutai-stt-rs" # Espérer qu'il soit dans le PATH

    def transcribe(self, audio_input, language="fr"):
        """
        Transcrit l'audio (chemin de fichier ou numpy array) et renvoie les segments.
        """
        if self.provider == "whisper":
            if isinstance(audio_input, str):
                segments, info = self.model.transcribe(audio_input, beam_size=5, language=language)
            else:
                segments, info = self.model.transcribe(audio_input, beam_size=5, language=language)
            
            # Conversion en liste de dicts
            return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
            
        elif self.provider == "kyutai":
            return list(self._transcribe_kyutai(audio_input))
        elif self.provider == "kyutai_mlx":
            return list(self._transcribe_kyutai_mlx(audio_input))
        elif self.provider == "kyutai_stt":
            return list(self._transcribe_kyutai_stt(audio_input))

    def _transcribe_kyutai_stt(self, audio_input):
        import torch
        import librosa
        import re
        
        target_sr = 24000
        if isinstance(audio_input, str):
            audio, sr = librosa.load(audio_input, sr=target_sr)
        else:
            audio = audio_input
            sr = 16000 # On reçoit du 16kHz depuis le segmenter
            # Rééchantillonnage vers 24kHz car Kyutai l'exige
            if sr != target_sr:
                audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
                sr = target_sr
        
        inputs = self.processor(audio=audio, sampling_rate=sr, return_tensors="pt").to(self.device)
        
        try:
            max_audio_frames = inputs["input_values"].shape[-1] // self.model.config.codec_config.frame_size
            max_new_tokens = min(4096, max_audio_frames) 
        except:
            max_new_tokens = 2048

        import time
        start_gen = time.time()
        with torch.no_grad():
            output_tokens = self.model.generate(
                **inputs, 
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=1
            )
        duration_gen = time.time() - start_gen
        
        full_text = self.processor.batch_decode(output_tokens, skip_special_tokens=True)[0].strip()
        print(f"DEBUG [Kyutai]: Texte brut décodé en {duration_gen:.2f}s: \"{full_text}\"")
        
        if full_text:
            sentences = re.split(r'(?<=[.!?])\s+', full_text)
            total_duration = len(audio) / sr
            for i, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if len(sentence) < 3:
                    continue
                
                yield {
                    "start": (i / len(sentences)) * total_duration if len(sentences) > 0 else 0,
                    "end": ((i + 1) / len(sentences)) * total_duration if len(sentences) > 0 else total_duration,
                    "text": sentence
                }

    def _transcribe_kyutai_mlx(self, audio_input):
        import librosa
        from moshi_mlx import models
        
        if isinstance(audio_input, str):
            audio, _ = librosa.load(audio_input, sr=24000, mono=True)
        else:
            audio = audio_input
            
        in_pcms = audio[np.newaxis, :]
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

    def _transcribe_kyutai(self, audio_input):
        if not isinstance(audio_input, str):
            # Temporairement sauvegarder en wav si c'est un array
            import soundfile as sf
            import tempfile
            temp_wav = tempfile.mktemp(suffix=".wav")
            sf.write(temp_wav, audio_input, 24000)
            input_path = temp_wav
        else:
            input_path = audio_input
            
        cmd = [self.binary_path, input_path, "--timestamps", "--vad", "--cpu"]
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
        finally:
            if not isinstance(audio_input, str) and os.path.exists(temp_wav):
                os.remove(temp_wav)
