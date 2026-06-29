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
This model uses a **Random Forest** machine learning approach to detect radio chronicle segments from textual transcriptions (SRT files). It is designed to be a lightweight and efficient alternative for text-based segmentation.

Hugging Face link: [eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest](https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-randomforest)

## Model Details

The model is a single-file classifier (`.pkl`) serialized with `joblib`. It operates by analyzing individual transcription segments and their immediate context.

### 1. Feature Engineering
The model extracts several key features from the SRT segments:
*   **Temporal Data**: Precise air time and segment duration.
*   **Linguistic Statistics**: Word count, character count, and average word length.
*   **Punctuation Analysis**: Detection of question marks and exclamation points to identify rhetorical styles.
*   **TF-IDF Vectorization**: A statistical measure used to evaluate the importance of words in the transcript relative to radio chronicle vocabulary.
*   **Jingle Detection**: Specific binary markers for identified radio jingles.

### 2. Contextual Awareness (Sliding Window)
To improve accuracy, the model employs a **sliding window** technique. It doesn't just look at a segment in isolation; it incorporates features from the surrounding segments (e.g., the 2 segments before and 2 segments after) to capture the flow and continuity of the radio broadcast.

### 3. Core Classifier
The underlying algorithm is a **RandomForestClassifier** from the Scikit-Learn library, optimized with 200 estimators to handle the balance between precision and recall for chronicle detection.

## Advantages
*   **CPU-Only**: Does not require any GPU or heavy deep learning frameworks.
*   **High Speed**: Processing an hour-long show takes less than a second.
*   **Efficiency**: Extremely low memory footprint.

## Usage
The model is integrated into the local `predict.py` workflow:
```python
from train import RadioChroniqueClassifier
classifier = RadioChroniqueClassifier.load_model("models/radio_chronique_rf.pkl")
```

## Author
Maintained by eglantinefonrose.
