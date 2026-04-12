---
tags:
- audiotranscription-segmentation
- radio
- radio-live-a-la-carte
- rlac
model_index:
- name: RLAC Audio-transcription Detector (Segment aka Column aka Feature vs Ads/Transitions/...)
---

# RLAC Audio-transcription Segmenter - Chroniques

## Description
This is version 0.1 of a ...

Hugging Face link: [eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid](https://huggingface.co/eglantinefonrose/rlac-audiotranscript-segmenter-chroniques-hybrid)

## Model Details 

Les deux fichiers présents sont les deux composants indissociables d'une même approche hybride pour la détection des chroniques :

  1. Fichier `radio_chronique_hybrid_base.pkl` (L'extracteur de caractéristiques)
  Ce fichier est un objet Python (sérialisé avec joblib) qui gère la transformation du texte brut en données numériques.
   * Rôle : Il sert de "pré-processeur". Il extrait pour chaque segment de transcription :
       * Des caractéristiques de base : durée du segment, nombre de mots, ponctuation, présence de jingles, et l'heure de passage.
       * Des caractéristiques textuelles (TF-IDF) : statistiques sur le vocabulaire utilisé.
       * Des embeddings BERT : il utilise le modèle CamemBERT pour comprendre le sens sémantique profond du texte.
   * Format : C'est un objet RadioChroniqueClassifier qui contient également le scaler (pour normaliser les données) et le tfidf_vectorizer.

  2. Fichier `radio_chronique_hybrid_hybrid.pt` (Le classifieur séquentiel)
  Ce fichier est un modèle de Deep Learning (PyTorch) qui prend les données préparées par le modèle "base" pour prendre la décision finale.
   * Architecture : Il utilise une couche Bi-LSTM (Bidirectional Long Short-Term Memory) suivie d'une couche CRF (Conditional Random Field).
   * Rôle : Contrairement à un modèle classique qui regarderait chaque segment isolément, celui-ci analyse la séquence entière. Il comprend qu'une chronique a un début, un milieu et une fin. Le CRF garantit que la séquence prédite est cohérente (par
     exemple, on ne peut pas avoir un "milieu de chronique" sans avoir eu un "début").
   * Particularité : Il a été entraîné avec une Focal Loss pour mieux détecter les débuts de chroniques, qui sont des événements rares par rapport au reste du flux audio.

  En résumé : 
  Le fichier .pkl est l'intelligence qui comprend le texte, tandis que le fichier .pt est l'intelligence qui comprend le rythme et la structure de l'émission. Pour effectuer une prédiction, le script predict.py charge et utilise les deux simultanément.


## Usage
...

## Author
Maintained by eglantinefonrose.
