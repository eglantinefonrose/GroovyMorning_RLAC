# The Journey of Training Text Models for Chronicle Detection

This article traces the technical evolution and methodological steps followed to train models capable of
automatically detecting radio chronicles by analyzing the textual content from the transcription (Speech-to-Text) of audio streams.

## Introduction: General Methodology

Segment detection via text is based on the analysis of linguistic sequences. Unlike the audio approach which
relies on sound textures, this method exploits semantics, discourse structure, and textual markers
(introductory formulas, transitions) to isolate chronicles within a transcription.

We explored three major paths:
1. The "Semantic Intelligence" Approach (LLM & Few-Shot): Using the reasoning power of language models (Mistral,
   Claude, DeepSeek) via structured prompts to identify segments.
2. The "Statistical Analysis" Approach (Classical NLP): Extracting textual features (TF-IDF, sliding windows) and
   using lightweight classifiers like Random Forest.
3. The "Semantic Deep Learning" Approach (Fine-Tuning BERT): Specializing French language models (CamemBERT) for
   segment classification or precise detection of lead-in sentences.

### Tracking and Reproducibility of Training Sessions
To ensure rigorous traceability of our textual experiments, we use the Weights & Biases (WandB) platform. This
tool allows us to centralize:
- Metric monitoring: real-time tracking of loss and precision scores (F1-score) on text labels.
- Hardware configuration: recording the resources used for fine-tuning phases.
- Hyperparameter archiving: keeping track of configurations (context window size, learning rate) to
  identify the best-performing architectures.

### Performance Evaluation (RLAC Scoring)
The quality of text models is subject to the same demanding scoring system as the rest of the RLAC project:
- Cardinality (40%): The model's ability not to miss chronicles and not to invent false segments in the
  text.
- Temporal Alignment (60%): The precision of the timecodes extracted from the transcription (SRT) to mark the exact
  start and end of the intervention.

### Publication and Deployment
All text classification and chronicle start detection models are published on the project's Hugging Face
space.