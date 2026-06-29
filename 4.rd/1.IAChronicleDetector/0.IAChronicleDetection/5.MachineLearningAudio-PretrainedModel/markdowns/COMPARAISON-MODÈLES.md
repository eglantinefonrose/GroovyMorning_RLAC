# Comparaison des Modèles pour la Détection de Chroniques

Ce document présente une critique technique du modèle actuel et propose des alternatives pour améliorer les performances de détection des chroniques radio.

## 1. Critique du Modèle Actuel (Wav2Vec2 XLS-R)

Le modèle `facebook/wav2vec2-large-xlsr-53-french` est actuellement utilisé. Bien qu'excellent pour la reconnaissance vocale (ASR), il présente des limites pour la classification de segments :

*   **Biais linguistique :** Wav2Vec2 est optimisé pour reconnaître des phonèmes et des mots. Or, une chronique se détecte souvent par sa **texture sonore** (jingles, musique de fond, qualité acoustique) que Wav2Vec2 peut avoir tendance à ignorer.
*   **Lourdeur vs Tâche :** La version `large` (300M+ paramètres) est lourde pour une classification binaire ou multi-classes simple. Cela ralentit l'inférence et nécessite plus de données pour éviter le sur-apprentissage (overfitting).
*   **Analyse Locale :** Le traitement séquentiel de l'onde brute peut manquer de vision "globale" sur un segment de 10s, notamment pour identifier des motifs musicaux complexes (jingles).

---

## 2. Modèles Alternatifs Suggérés

Pour améliorer la détection basée sur l'identité sonore globale, voici les architectures recommandées :

### A. AST (Audio Spectrogram Transformer)
*   **Description :** Convertit l'audio en spectrogramme (image) et utilise un Transformer (ViT) pour l'analyse.
*   **Pourquoi :** Excellent pour capturer les signatures acoustiques et les jingles. C'est souvent le meilleur compromis pour la classification de scènes sonores.
*   **Modèle suggéré :** `MIT/ast-finetuned-audioset-10-10-0.4593`

### B. BEATs (Iterative Audio Pre-training)
*   **Description :** Un des modèles SOTA (State of the Art) pour la classification sonore générale.
*   **Pourquoi :** Entraîné pour capturer à la fois la parole et les sons environnementaux/musicaux. Très robuste au bruit et aux mélanges sonores.
*   **Modèle suggéré :** `microsoft/beats-base`

### C. WavLM (Wave Latent Measurement)
*   **Description :** Une évolution de Wav2Vec2 conçue pour le traitement global de la parole.
*   **Pourquoi :** Contrairement à Wav2Vec2, il est entraîné sur des tâches de séparation de sources et d'identification de locuteurs. Il gère mieux les fonds musicaux sous la voix.
*   **Modèle suggéré :** `microsoft/wavlm-base-plus-sv`

### D. CNN (EfficientNet / ResNet) sur Spectrogrammes
*   **Description :** Approche classique traitant l'audio comme une image via des spectrogrammes de Mel.
*   **Pourquoi :** Très léger et extrêmement rapide à l'inférence. Très efficace pour reconnaître des motifs visuels répétitifs comme les jingles.

---

## 3. Pistes d'Amélioration Stratégiques

### Approche Hybride (Détection de Jingle)
Au lieu de classer uniquement des segments de 10s, entraîner un modèle léger spécifique à la reconnaissance des **jingles d'introduction**. La détection d'un jingle est un indicateur de confiance quasi-absolu pour le début d'une chronique.

### Segmentation Hiérarchique
1.  Utiliser un modèle très léger pour filtrer le "silence" et la "musique pure".
2.  Passer uniquement les segments contenant de la parole au modèle de classification (AST ou WavLM).

### Augmentation de Données (Data Augmentation)
Améliorer la robustesse en ajoutant artificiellement durant l'entraînement :
*   Du bruit de fond varié.
*   Des variations de volume (gain aléatoire).
*   Des légers changements de pitch ou de vitesse (time stretching).

### Vote Majoritaire / Fenêtre Glissante
Affiner l'inférence en faisant prédire le modèle sur des fenêtres de tailles différentes (ex: 5s, 10s, 15s) et en moyennant les probabilités pour lisser les prédictions et éviter les coupures intempestives.
