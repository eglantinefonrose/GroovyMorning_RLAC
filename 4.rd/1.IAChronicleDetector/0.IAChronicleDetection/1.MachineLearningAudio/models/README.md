---
tags:
- audio-segmentation
- radio
- radio-live-a-la-carte
- rlac
model_index:
- name: RLAC Audio Detector (Segment aka Column aka Feature vs Ads/Transitions/...)
---

# RLAC Audio Segmenter - Chroniques

## Description
This is version 0.1 of a Random Forest classifier designed for radio audio segmentation. It identifies specific audio segments (columns, features, or ads) within long radio broadcasts.

https://huggingface.co/eglantinefonrose/rlac-audio-segmenter-chroniques

## Model Details
- Type: Random Forest Classifier
- Input: 3-second audio segments
- Features: MFCC (13), Spectral Energy (4 bands), Zero-Crossing Rate, RMS, Spectral Centroid, Rolloff, and Bandwidth.
- Version: v0.1

## Usage
The model is trained to distinguish between targeted content and background broadcast material. It uses a confidence threshold of 0.89 to minimize false positives during the detection phase.

## Author
Maintained by eglantinefonrose.
