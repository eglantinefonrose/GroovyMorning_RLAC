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
- name: camembert-chronicle-start-detection-v4
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# camembert-chronicle-start-detection-v4

This model was trained from scratch on an unknown dataset.
It achieves the following results on the evaluation set:
- Loss: 0.5229
- Accuracy: 0.7637
- F1: 0.3488
- Precision: 0.6923
- Recall: 0.2332

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
| No log        | 1.0   | 319  | 0.5368          | 0.7496   | 0.2193 | 0.7143    | 0.1295 |
| 0.5454        | 2.0   | 638  | 0.5468          | 0.7328   | 0.0404 | 0.8       | 0.0207 |
| 0.5454        | 3.0   | 957  | 0.5229          | 0.7637   | 0.3488 | 0.6923    | 0.2332 |
| 0.5090        | 4.0   | 1276 | 0.5271          | 0.7637   | 0.3488 | 0.6923    | 0.2332 |
| 0.4795        | 5.0   | 1595 | 0.5337          | 0.7595   | 0.2963 | 0.72      | 0.1865 |


### Framework versions

- Transformers 5.9.0
- Pytorch 2.8.0
- Tokenizers 0.22.2
