import os
import torch
from transformers import (
    ASTForAudioClassification,
    ASTFeatureExtractor,
    AutoModelForAudioClassification,
    AutoFeatureExtractor,
    WavLMForSequenceClassification,
    Wav2Vec2FeatureExtractor,
    Wav2Vec2ForSequenceClassification
)

BASE_MODELS = {
    "ast": "MIT/ast-finetuned-audioset-10-10-0.4593",
    "beats": "microsoft/beats-base",
    "cnn": "MIT/efficientnet-b0-audioset",
    "wavlm": "microsoft/wavlm-base-plus-sv",
    "wav2vec2": "facebook/wav2vec2-base-960h"
}

class ModelLoader:
    def __init__(self, device=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
        self.models = {}
        self.extractors = {}

    def _get_effective_path(self, path):
        """Returns the path itself if weights are present, or the latest checkpoint subdirectory."""
        if not os.path.exists(path):
            return path
        
        # Check for standard weight files
        weight_files = ["model.safetensors", "pytorch_model.bin", "model.ckpt"]
        if any(os.path.exists(os.path.join(path, f)) for f in weight_files):
            return path
            
        # Try to find checkpoints
        checkpoints = [d for d in os.listdir(path) if d.startswith("checkpoint-") and os.path.isdir(os.path.join(path, d))]
        if checkpoints:
            # Sort by checkpoint number
            checkpoints.sort(key=lambda x: int(x.split("-")[1]))
            latest = os.path.join(path, checkpoints[-1])
            print(f"No weights found at root of {path}, using latest checkpoint: {latest}")
            return latest
            
        return path

    def load_ast(self, path="./model_output_ast"):
        eff_path = self._get_effective_path(path)
        print(f"Loading AST from {eff_path}...")
        self.models["ast"] = ASTForAudioClassification.from_pretrained(eff_path).to(self.device)
        self.extractors["ast"] = ASTFeatureExtractor.from_pretrained(eff_path)
        self.models["ast"].eval()

    def load_beats(self, path="./model_output_beats"):
        eff_path = self._get_effective_path(path)
        print(f"Loading BEATS from {eff_path}...")
        self.models["beats"] = AutoModelForAudioClassification.from_pretrained(eff_path).to(self.device)
        self.extractors["beats"] = AutoFeatureExtractor.from_pretrained(eff_path)
        self.models["beats"].eval()

    def load_cnn(self, path="./model_output_cnn"):
        eff_path = self._get_effective_path(path)
        print(f"Loading CNN (EfficientNet) from {eff_path}...")
        self.models["cnn"] = AutoModelForAudioClassification.from_pretrained(eff_path).to(self.device)
        self.extractors["cnn"] = AutoFeatureExtractor.from_pretrained(eff_path)
        self.models["cnn"].eval()

    def load_wavlm(self, path="./model_output_wavlm"):
        eff_path = self._get_effective_path(path)
        print(f"Loading WavLM from {eff_path}...")
        self.models["wavlm"] = WavLMForSequenceClassification.from_pretrained(eff_path).to(self.device)
        self.extractors["wavlm"] = Wav2Vec2FeatureExtractor.from_pretrained(eff_path)
        self.models["wavlm"].eval()

    def load_wav2vec2(self, path="./model_output"):
        eff_path = self._get_effective_path(path)
        print(f"Loading Wav2Vec2 from {eff_path}...")
        self.models["wav2vec2"] = Wav2Vec2ForSequenceClassification.from_pretrained(eff_path).to(self.device)
        self.extractors["wav2vec2"] = Wav2Vec2FeatureExtractor.from_pretrained(eff_path)
        self.models["wav2vec2"].eval()

    def load_base(self, name):
        """Loads a base model from Hugging Face instead of local path."""
        repo_id = BASE_MODELS.get(name)
        if not repo_id:
            print(f"Unknown base model: {name}")
            return
            
        print(f"Preloading base model {name} from {repo_id}...")
        try:
            if name == "ast":
                self.models["ast"] = ASTForAudioClassification.from_pretrained(repo_id).to(self.device)
                self.extractors["ast"] = ASTFeatureExtractor.from_pretrained(repo_id)
            elif name == "beats" or name == "cnn":
                self.models[name] = AutoModelForAudioClassification.from_pretrained(repo_id).to(self.device)
                self.extractors[name] = AutoFeatureExtractor.from_pretrained(repo_id)
            elif name == "wavlm":
                self.models["wavlm"] = WavLMForSequenceClassification.from_pretrained(repo_id).to(self.device)
                self.extractors["wavlm"] = Wav2Vec2FeatureExtractor.from_pretrained(repo_id)
            elif name == "wav2vec2":
                self.models["wav2vec2"] = Wav2Vec2ForSequenceClassification.from_pretrained(repo_id).to(self.device)
                self.extractors["wav2vec2"] = Wav2Vec2FeatureExtractor.from_pretrained(repo_id)
            
            if name in self.models:
                self.models[name].eval()
        except Exception as e:
            print(f"Failed to preload {name}: {e}")

    def load_all(self, use_base_fallback=False):
        # Local paths mapping
        paths = {
            "ast": "./model_output_ast",
            "beats": "./model_output_beats",
            "cnn": "./model_output_cnn",
            "wavlm": "./model_output_wavlm",
            "wav2vec2": "./model_output"
        }
        
        for name, path in paths.items():
            if os.path.exists(path):
                getattr(self, f"load_{name}")(path)
            elif use_base_fallback:
                self.load_base(name)

    def get_model(self, name):
        return self.models.get(name), self.extractors.get(name)

    # Methods for Fine-Tuning Initialization
    def init_wav2vec2(self, model_name_or_path, label2id, id2label):
        print(f"Initializing Wav2Vec2 for fine-tuning from {model_name_or_path}...")
        model = Wav2Vec2ForSequenceClassification.from_pretrained(
            model_name_or_path, num_labels=2, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        )
        extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name_or_path)
        return model, extractor

    def init_ast(self, model_name_or_path, label2id, id2label):
        print(f"Initializing AST for fine-tuning from {model_name_or_path}...")
        model = ASTForAudioClassification.from_pretrained(
            model_name_or_path, num_labels=2, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        )
        extractor = ASTFeatureExtractor.from_pretrained(model_name_or_path)
        return model, extractor

    def init_beats(self, model_name_or_path, label2id, id2label):
        print(f"Initializing BEATS for fine-tuning from {model_name_or_path}...")
        model = AutoModelForAudioClassification.from_pretrained(
            model_name_or_path, num_labels=2, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        )
        extractor = AutoFeatureExtractor.from_pretrained(model_name_or_path)
        return model, extractor

    def init_cnn(self, model_name_or_path, label2id, id2label):
        print(f"Initializing CNN for fine-tuning from {model_name_or_path}...")
        model = AutoModelForAudioClassification.from_pretrained(
            model_name_or_path, num_labels=2, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        )
        extractor = AutoFeatureExtractor.from_pretrained(model_name_or_path)
        return model, extractor

    def init_wavlm(self, model_name_or_path, label2id, id2label):
        print(f"Initializing WavLM for fine-tuning from {model_name_or_path}...")
        model = WavLMForSequenceClassification.from_pretrained(
            model_name_or_path, num_labels=2, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        )
        extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name_or_path)
        return model, extractor

if __name__ == "__main__":
    loader = ModelLoader()
    # Now we can ask to load all, and use base models if local ones are missing
    loader.load_all(use_base_fallback=True)
    print(f"Loaded models for prediction: {list(loader.models.keys())}")
