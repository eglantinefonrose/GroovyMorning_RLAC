## Introduction: General Methodology

Audio segment detection is based on a **sequence classification** approach. The fundamental idea is to divide a continuous audio stream into temporal segments and assign a label to each segment (e.g., "Chronicle X", "Advertisement", or "Background Noise").

We explored two major paths:
1.  **The "Acoustic Characterization" Approach (Classical ML)**: Extracting mathematical signatures (MFCC, energy) and using classic classifiers (Random Forest).
2.  **The "Deep Learning / Fine-Tuning" Approach**: Using a pre-trained speech recognition model (like Wav2Vec2) and specializing it on our specific data.

### Tracking and Reproducibility of Training Sessions
To ensure rigorous traceability of our experiments, we use the Weights & Biases (WandB) platform. This tool allows us to centralize:
- Metric monitoring: real-time tracking of loss and precision scores (F1-score) during training.
- Hardware configuration: recording machine characteristics (GPU, CPU, memory) to guarantee the reproducibility of results.
- Hyperparameter archiving: keeping track of each configuration tested to identify the best-performing models.

### Performance Evaluation (RLAC Scoring)
Model quality is not limited to simple statistical precision. We have implemented a specific scoring system for the RLAC project, based on two major criteria:
- Cardinality (40%): The model's ability to identify the exact number of chronicles present, without omissions or over-segmentation.
- Temporal Alignment (60%): The surgical precision of the start and end points of each detected chronicle compared to reality.

### Publication and Deployment
All models are published on the project's Hugging Face space.

[Version Française](../../../fr/ia-models-training/audio/ARTICLE_INTRO_AUDIO.md)
