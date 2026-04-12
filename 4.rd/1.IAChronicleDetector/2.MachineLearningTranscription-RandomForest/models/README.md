---
tags:
- audiotranscription-segmentation
- radio
- radio-live-a-la-carte
- rlac
- random-forest
- transcription
model_index:
- name: RLAC Audio-transcription Segmenter - Chroniques (Random Forest)
---

# RLAC Audio-transcription Segmenter - Chroniques (Random Forest)

## Description
This model uses a classical **Machine Learning (Random Forest)** approach to detect radio chronicle segments from textual transcriptions (SRT files).

Hugging Face link: [eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest](https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest)

## Model Details

The model is encapsulated in a `.pkl` file (serialized with `joblib`) and relies on the following components:

### 1. Feature Extraction
For each transcription segment, the model analyzes:
*   **Temporal metadata**: Air time, segment duration.
*   **Textual statistics**: Word count, average word length, presence of specific punctuation (question marks, exclamation points).
*   **Vocabulary Analysis (TF-IDF)**: A vectorizer identifies recurring keywords in radio chronicles.
*   **Specific markers**: Detection of jingles or predefined keywords.

### 2. Sequential Context (Sliding Window)
Unlike word-by-word classification, this model uses a **sliding window**. To decide if a segment belongs to a chronicle, it also examines the features of the immediately preceding and following segments. This helps better capture the continuity of a radio segment.

### 3. Classifier
The core of the model is a **RandomForestClassifier** (Scikit-Learn) trained to distinguish chronicle segments from the rest of the stream (advertisements, transitions, music).

## Advantages
*   **Lightweight**: No need for GPU or heavy Deep Learning libraries.
*   **Fast**: Inference is near-instantaneous on a standard processor.
*   **Interpretable**: The features influencing the decision can be analyzed.

## Usage
The model is loaded and used by the `train.py` and `predict.py` scripts of the project:
```python
from train import RadioChroniqueClassifier
classifier = RadioChroniqueClassifier.load_model("models/radio_chronique_rf.pkl")
```

## Author
Maintained by eglantinefonrose.
