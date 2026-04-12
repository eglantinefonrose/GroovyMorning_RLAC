# Spécifications : RLAC Timecode Verification Tool

## 1. Contexte et Genèse des données

Ce projet s'inscrit dans un workflow d'automatisation du découpage et de l'indexation de contenus radiophoniques (notamment la matinale de France Inter). Les données manipulées par cet outil proviennent d'une chaîne de traitement IA complexe :

### 1.1 La Transcription (Whisper)
Les fichiers audio sont d'abord transcrits par les modèles **Whisper** d'OpenAI. Dans ce projet, on utilise principalement des variantes haute performance comme `whisper-large-v3-turbo`. Bien que ces modèles soient extrêmement précis pour le texte, le "timestamping" (horodatage) au niveau du mot ou de la phrase peut parfois présenter des micro-décalages par rapport à l'audio réel (notamment en présence de jingles ou de bruits de fond).

### 1.2 Le Découpage Sémantique (LLM)
Une fois la transcription obtenue, des modèles de langage (LLM) comme **Gemini 1.5 Flash ou Pro** sont utilisés pour analyser le texte et identifier les limites théoriques des chroniques. Ces modèles comparent la transcription avec les programmes officiels (fichiers JSON théoriques) pour "deviner" où commence et s'arrête chaque séquence.

### 1.3 Le Besoin de Validation (Human-in-the-loop)
L'automatisation produit des résultats impressionnants mais pas parfaits. Il existe souvent un écart entre :
- **Le début sémantique** (le moment où l'IA comprend que le sujet change).
- **Le début sonore** (le premier souffle du jingle ou l'annonce exacte du journaliste).

L'outil **RLAC Timecode Verification** a été conçu pour permettre à un opérateur humain de valider ou de corriger ces écarts en quelques secondes par séquence, en utilisant la transcription comme guide visuel pour "cliquer" sur le point d'ancrage sonore exact.

## 2. Objectif
Outil macOS natif (SwiftUI) permettant la validation et la correction manuelle ultra-rapide des segments temporels d'une émission radio. L'outil permet de naviguer au clavier dans une liste de séquences et de corriger les bornes temporelles en interagissant directement avec le texte de la transcription.

## 2. Architecture & Environnement
- **Plateforme :** macOS 14+ (SwiftUI)
- **Moteur Audio :** `AVPlayer` (pour la lecture interactive et le seek précis)
- **Outil CLI :** `FFmpeg` (pour les opérations de découpage ou de traitement futur)
- **Configuration :** Fichier JSON local stockant les chemins des répertoires préférés.

## 3. Gestion des Fichiers et Nommage

### 3.1 Règle de correspondance
Pour un média donné `[NOM]`, l'application lie automatiquement :
- **Audio :** `[NOM].mp3`
- **Transcription :** `[NOM]_transcription.srt`
- **Timecodes :** `[NOM]_timecode_chronique.txt`

### 3.2 Sauvegarde et Traçabilité
Lors de la première modification manuelle d'un fichier de timecodes :
1. L'application vérifie l'existence d'un sous-répertoire `.original_before_manual_correction` dans le dossier des Timecodes.
2. Elle y déplace une copie du fichier original avant d'écraser le fichier dans le répertoire principal.

## 4. Interface Utilisateur (UI)

### 4.1 Barre Supérieure (Header)
- **Sélecteur de fichier (Combo Box) :** Liste les fichiers `.mp3` du répertoire média.
- **Réglages de lecture :** 
    - Champ `X` : secondes à lire au début (ex: 5s).
    - Champ `Y` : secondes à lire à la fin (ex: 3s).
- **Toggle Autoplay :** Active/Désactive la lecture automatique lors de la navigation.

### 4.2 Panneau Gauche (Navigation)
- **Liste des séquences :** Liste verticale des segments extraits du fichier `.txt`.
- **État :** Affiche visuellement si la séquence a été "vue" ou "modifiée".
- **Navigation :** `Flèche Haut / Bas` pour changer de focus.

### 4.3 Panneau Central (Transcription & Édition)
- **Mode Visualisation :** Affiche le texte de la séquence actuelle (blocs SRT concaténés).
- **Mode Édition (Activé par `Espace`) :**
    - Affiche une vue "Timeline" de texte incluant les blocs SRT immédiatement avant et après la séquence.
    - Chaque bloc de texte est cliquable.
    - **Logique de clic intelligent :** 
        - Si le timecode du bloc cliqué est plus proche du `Début` actuel de la séquence, il met à jour le `Début`.
        - Sinon, il met à jour la `Fin`.

## 5. Workflow de l'utilisateur

### 5.1 Validation (Mode Rapide)
1. L'utilisateur sélectionne un média.
2. Il descend dans la liste avec `Flèche Bas`.
3. L'application joue automatiquement : `[Début -> Début + X]` puis saute à `[Fin - Y -> Fin]`.
4. Si le son correspond au texte, il continue.

### 5.2 Correction (Mode Édition)
1. Si un décalage est entendu, l'utilisateur appuie sur `Espace`.
2. Il identifie visuellement dans le texte étendu le moment exact où la chronique commence ou finit.
3. Il clique sur le texte correspondant.
4. L'UI se met à jour, et il peut réécouter pour valider.

## 6. Commandes Clavier
- `Flèche Bas / Haut` : Sélectionner la séquence suivante / précédente.
- `Espace` : Basculer le mode édition (affiche le contexte textuel étendu).
- `L` : Rejouer l'aperçu (Début X + Fin Y) de la séquence sélectionnée.
- `S` : Sauvegarder manuellement (bien que la sauvegarde puisse être automatique à la modification).

## 7. Configuration technique
L'application doit permettre de définir via un menu "Préférences" ou un fichier de config :
- `mediaDirectoryPath`: String
- `transcriptionDirectoryPath`: String
- `timecodeDirectoryPath`: String
- `defaultXSeconds`: Int (default 5)
- `defaultYSeconds`: Int (default 3)
