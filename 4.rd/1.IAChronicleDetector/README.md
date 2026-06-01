# IA Chronicle Detector

Ce projet explore différentes approches technologiques pour détecter automatiquement les chroniques au sein d'émissions de radio. Plusieurs méthodes ont été testées, allant de l'analyse audio brute au traitement avancé du langage naturel (NLP) sur des transcriptions.

## Synthèse des Méthodes Testées

### 0. Transcription + LLM (Prompt Engineering)
**Répertoire :** `0.TranscriptionAndLLMMethod/`
*   **Technique :** Utilisation de modèles de langage (LLM) pour analyser les transcriptions textuelles. L'approche repose sur le *prompt engineering* en fournissant au modèle le contexte de l'émission et éventuellement une liste de chroniques attendues.
*   **Résultats :** Très performant avec des modèles en ligne puissants (type GPT-4), mais moins efficace avec des modèles locaux légers. Le coût et la fenêtre de contexte sont les principaux points d'attention.

### 1. Machine Learning Audio
**Répertoire :** `1.MachineLearningAudio/`
*   **Technique :** Analyse directe du signal sonore par segmentation (fenêtres de 3s). Extraction de caractéristiques acoustiques : **MFCC**, **ZCR**, **énergie spectrale**, **RMS**. Classification via **Random Forest**, **SVM** ou **MLP**.
*   **Résultats :** Peu concluant. La méthode peine à distinguer finement les chroniques des publicités ou des passages musicaux, entraînant des segmentations imprécises ou des coupures brutales.

### 2. ML Transcription - Random Forest
**Répertoire :** `2.MachineLearningTranscription-RandomForest/`
*   **Technique :** Approche textuelle légère basée sur les fichiers SRT. Utilise des caractéristiques statistiques (nombre de mots, durée) et sémantiques simples (**TF-IDF**) avec une fenêtre glissante pour le contexte. Classification via **Random Forest**.
*   **Résultats :** Rapide, efficace et ne nécessite pas de GPU. C'est un excellent compromis entre complexité et performance pour une détection de base.

### 3. ML Transcription - Hybride (Deep Learning)
**Répertoire :** `3.MachineLearningTranscription-Hybrid/`
*   **Technique :** Architecture complexe combinant trois couches :
    1.  **CamemBERT** : Embeddings sémantiques profonds.
    2.  **Bi-LSTM** : Analyse de la structure séquentielle de l'émission.
    3.  **CRF** : Optimisation de la cohérence temporelle des prédictions.
*   **Résultats :** Très précis car il comprend à la fois le sens des mots et l'ordre logique d'une émission. Nécessite cependant des ressources de calcul plus importantes (GPU/MPS).

### 4. Transformer Detection (Fine-tuning)
**Répertoire :** `4.TransformerDetection/`
*   **Technique :** **Fine-tuning** direct d'un modèle **CamemBERT** sur la tâche de classification de segments. Utilise une gestion de fenêtre contextuelle et un système de scoring spécifique.
*   **Résultats :** Excellente détection des frontières de chroniques. C'est actuellement l'approche la plus robuste pour identifier précisément les points de bascule.

---

## Glossaire Technique

### Traitement du Signal (Audio)
*   **MFCC (Mel-Frequency Cepstral Coefficients)** : Représentation du spectre sonore qui reproduit la manière dont l'oreille humaine perçoit les fréquences. C'est en quelque sorte "l'empreinte digitale" ou le timbre de la voix.
*   **ZCR (Zero-Crossing Rate)** : Mesure la fréquence à laquelle le signal sonore croise la ligne du zéro. Un ZCR élevé indique souvent du bruit ou des sons percussifs, tandis qu'un ZCR bas est typique de la voix humaine.
*   **Énergie Spectrale** : Analyse de la répartition de la puissance sonore dans les différentes bandes de fréquences (graves, médiums, aigus). Elle permet de distinguer un passage parlé d'un passage musical.
*   **RMS (Root Mean Square)** : Mesure de l'intensité globale ou du volume moyen d'un segment audio. Cela aide à identifier les variations de puissance sonore entre le plateau radio et les jingles.

### Machine Learning & NLP
*   **TF-IDF (Term Frequency-Inverse Document Frequency)** : Technique statistique qui évalue l'importance d'un mot dans un texte par rapport à une collection de documents. Cela permet d'isoler les mots "signatures" d'une chronique.
*   **Random Forest (Forêt Aléatoire)** : Algorithme qui combine les prédictions de nombreux arbres de décision pour produire un résultat plus stable et robuste.
*   **SVM (Support Vector Machine / Machine à Vecteurs de Support)** : Algorithme qui cherche à tracer une frontière (appelée hyperplan) entre deux catégories de données. Sa particularité est de positionner cette frontière de manière à maximiser la distance ("marge") avec les points les plus proches de chaque groupe (les vecteurs de support). Cela garantit une meilleure robustesse face aux nouvelles données. Il peut également utiliser des "noyaux" (kernels) pour séparer des données qui ne le sont pas de façon linéaire.
*   **MLP (Multi-Layer Perceptron / Perceptron Multicouche)** : Type fondamental de réseau de neurones artificiels organisé en plusieurs couches : une couche d'entrée, une ou plusieurs couches "cachées" et une couche de sortie. Chaque "neurone" d'une couche est connecté à tous ceux de la couche suivante. Grâce à l'ajustement de ces connexions durant l'entraînement, le MLP peut apprendre des motifs extrêmement complexes et non-linéaires dans les données.
*   **CamemBERT** : Modèle de langage basé sur l'architecture **Transformer** (comme GPT ou BERT) et spécifiquement entraîné sur la langue française. La révolution des Transformers réside dans le mécanisme d'**attention** : au lieu de lire un texte mot à mot, le modèle analyse simultanément toutes les relations entre les mots d'une phrase. Cela lui permet de comprendre précisément le contexte (par exemple, distinguer le sens du mot "grève" selon qu'il est entouré de mots liés au travail ou au bord de mer) avec une finesse inégalée.
*   **Bi-LSTM (Bidirectional Long Short-Term Memory)** : Réseau de neurones qui analyse le texte dans les deux sens (passé et futur) pour capturer le contexte global d'une séquence.
*   **CRF (Conditional Random Fields)** : Modèle statistique qui assure la cohérence logique d'une séquence de prédictions (ex: une chronique ne peut pas se terminer avant d'avoir commencé).
*   **Fine-tuning (Affinage)** : Processus consistant à spécialiser un modèle d'IA déjà pré-entraîné sur une tâche très spécifique (ici, la détection de chroniques).

---
*Chaque sous-répertoire contient ses propres instructions d'installation et d'exécution.*
