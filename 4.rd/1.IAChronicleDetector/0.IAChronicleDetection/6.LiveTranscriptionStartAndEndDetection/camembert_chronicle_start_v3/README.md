---
library_name: transformers
tags:
- generated_from_trainer
metrics:
- accuracy
- f1
- precision
- recall
model-index:
- name: camembert-chronicle-start-detection-v3
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# camembert-chronicle-start-detection-v3

This model was trained from scratch on an unknown dataset.
It achieves the following results on the evaluation set:
- Loss: 0.6064
- Accuracy: 0.7090
- F1: 0.8297
- Precision: 0.7090
- Recall: 1.0

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 1e-05
- train_batch_size: 8
- eval_batch_size: 8
- seed: 42
- optimizer: Use OptimizerNames.ADAMW_TORCH_FUSED with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: linear
- lr_scheduler_warmup_steps: 0.1
- num_epochs: 5

### Training results

| Training Loss | Epoch | Step | Validation Loss | Accuracy | F1     | Precision | Recall |
|:-------------:|:-----:|:----:|:---------------:|:--------:|:------:|:---------:|:------:|
| No log        | 1.0   | 112  | 0.6064          | 0.7090   | 0.8297 | 0.7090    | 1.0    |
| No log        | 2.0   | 224  | 0.5962          | 0.7090   | 0.8297 | 0.7090    | 1.0    |
| No log        | 3.0   | 336  | 0.5957          | 0.7090   | 0.8297 | 0.7090    | 1.0    |
| No log        | 4.0   | 448  | 0.5972          | 0.7090   | 0.8297 | 0.7090    | 1.0    |


### Framework versions

- Transformers 5.9.0
- Pytorch 2.8.0
- Tokenizers 0.22.2
