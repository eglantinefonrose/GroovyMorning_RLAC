---
tags:
- audiotranscription-segmentation
- radio
- radio-live-a-la-carte
- rlac
- pytorch
- bert
- lstm
- crf
- transcription
model_index:
- name: RLAC Audio-transcription Segmenter - Chroniques (Hybrid CamemBERT + LSTM)
---

# RLAC Audio-transcription Segmenter - Chroniques (Hybrid)

## Description
This model uses a sophisticated **Hybrid Deep Learning** approach to detect radio chronicle segments from textual transcriptions (SRT files). It combines the semantic power of **CamemBERT** with the sequential modeling of a **Bi-LSTM + CRF** architecture.

Hugging Face link: [eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid](https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid)

## Model Details

This approach relies on two inseparable components that must be used together:

### 1. Feature Extractor & BERT Embeddings (`radio_chronique_hybrid_base.pkl`)
This file is a Python object (serialized with `joblib`) that manages the transformation of raw text into rich numerical vectors.
*   **Base Features**: Air time, segment duration, word count, punctuation patterns, and jingle detection.
*   **Semantic Embeddings**: It uses a **CamemBERT-base** model to extract high-dimensional semantic representations of the text.
*   **Normalization**: It contains the `scaler` and `tfidf_vectorizer` used during training.

### 2. Sequential Classifier (`radio_chronique_hybrid_hybrid.pt`)
This is a **PyTorch** model that takes the features prepared by the base extractor to make the final sequence-aware decision.
*   **Architecture**: A **Bi-LSTM** (Bidirectional Long Short-Term Memory) layer followed by a **CRF** (Conditional Random Field) layer.
*   **Sequential Logic**: Unlike simple classifiers that look at segments in isolation, this model analyzes the **entire flow of the show**. It understands that a chronicle has a beginning, a middle, and an end.
*   **Consistency**: The CRF layer ensures that the predicted sequence is logically consistent (e.g., an "inside chronicle" segment cannot exist without a preceding "start chronicle" segment).
*   **Training**: It was trained using **Focal Loss** to specifically improve the detection of chronicle starts, which are rare events in the data stream.

## Advantages
*   **Deep Understanding**: Uses BERT to understand the actual meaning of the words.
*   **Context Aware**: Analyzes the rhythm and structure of the radio show.
*   **High Precision**: The CRF layer significantly reduces false positives by enforcing temporal coherence.

## Usage
Both files are loaded and used by the `predict.py` script:
```python
from train import RadioChroniqueClassifier, HybridSequenceClassifier
base_extractor = RadioChroniqueClassifier.load_model("models/radio_chronique_hybrid_base.pkl")
hybrid_model = HybridSequenceClassifier.load("models/radio_chronique_hybrid_hybrid.pt")
```

## Author
Maintained by eglantinefonrose.
