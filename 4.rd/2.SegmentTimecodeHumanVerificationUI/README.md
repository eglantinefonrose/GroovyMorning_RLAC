# RLAC Timecode Verification Tool

Outil macOS natif (SwiftUI) conçu pour la validation et la correction ultra-rapide des segments temporels issus d'une chaîne de traitement IA (Whisper + LLM).

## Installation et Lancement

### Prérequis
- macOS 14.0 ou plus récent
- Xcode 15+ ou Swift 6.0+

### Compilation via le Terminal
1. Ouvrez le terminal dans le dossier du projet.
2. Compilez l'application :
   ```bash
   swift build
   ```
3. Lancez l'application :
   ```bash
   swift run
   ```

### Ouverture via Xcode
Vous pouvez également ouvrir le dossier racine dans Xcode. Xcode reconnaîtra le fichier `Package.swift` et vous permettra de lancer l'application avec `Cmd + R`.

## Configuration Initiale

Lors du premier lancement, vous devez configurer les répertoires de travail via les boutons dans la barre supérieure :
1. **Set Media Dir** : Dossier contenant vos fichiers `.mp3`.
2. **Set Transcr. Dir** : Dossier contenant les transcriptions `.srt`.
3. **Set Timecode Dir** : Dossier contenant les fichiers de segments `.txt`.

**Règle de nommage :** Pour un fichier `emission.mp3`, l'outil cherche `emission_transcription.srt` et `emission_timecode_chronique.txt`.

## Utilisation

### Workflow de Validation
1. **Sélectionner un fichier** dans le menu déroulant en haut à gauche.
2. **Naviguer** dans la liste des séquences (panneau de gauche) avec les **Flèches Haut/Bas**.
3. **Écouter** : Si "Autoplay" est coché, l'outil joue automatiquement les `X` premières secondes et les `Y` dernières secondes de la séquence pour vérifier les transitions.
4. **Valider** : Si le son correspond, passez à la suivante.

### Workflow de Correction
1. Si un décalage est détecté, appuyez sur **Espace** pour passer en **Mode Édition**.
2. Le panneau central affiche alors les blocs de texte SRT environnants.
3. **Cliquer sur un bloc de texte** pour mettre à jour le timecode :
   - Si vous cliquez sur un texte avant le début actuel, cela met à jour le point de **Début**.
   - Si vous cliquez vers la fin, cela met à jour le point de **Fin**.
4. Appuyez sur **L** pour réécouter l'aperçu corrigé.

## ⌨️ Raccourcis Clavier
- `Flèche Haut / Bas` : Sélectionner la séquence précédente / suivante.
- `Espace` : Basculer entre le mode Visualisation et le mode Édition.
- `L` : Rejouer l'aperçu (Launch preview).
- `S` : Sauvegarder manuellement les modifications.

## Sauvegarde et Backups
L'application sauvegarde automatiquement les modifications dans le fichier `.txt` d'origine. 
**Sécurité :** Lors de la toute première modification manuelle d'un fichier, une copie de l'original est automatiquement créée dans un sous-dossier `.original_before_manual_correction` pour éviter toute perte de données.
