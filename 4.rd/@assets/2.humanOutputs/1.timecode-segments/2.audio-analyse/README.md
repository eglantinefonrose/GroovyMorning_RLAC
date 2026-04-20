*(README réalisé avec Gemini CLI)*

# Analyse Audio : Recherche d'Occurrences

Ce dossier contient un outil d'analyse audio permettant de localiser précisément un extrait (chronique, jingle, publicité) au sein d'un enregistrement plus long (émission complète).

## Utilisation

Le script find_audio_occurrence.py s'utilise en ligne de commande. Il prend deux arguments : l'extrait à rechercher et le fichier complet.

```bash
python find_audio_occurrence.py <extrait.mp3> <audio_complet.mp3>
```

### Exemple :
```bash
python find_audio_occurrence.py chroniques/meteo.mp3 emissions/rtl_matin_06_04.mp3
```

## Prerequis

Le programme nécessite Python 3 et quelques bibliothèques spécialisées dans le traitement du signal. Vous pouvez les installer via pip :

```bash
pip install librosa numpy scipy
```

## Comment ca fonctionne ?

Le script utilise une technique mathématique appelée Corrélation Croisée via FFT (Fast Fourier Transform).

1. Chargement et Re-echantillonnage : Les deux fichiers sont chargés et convertis à un taux de 16 000 Hz. C'est suffisant pour identifier une signature sonore unique tout en garantissant une exécution rapide.
2. Normalisation : Les deux signaux sont centrés sur zéro et normalisés. Cela permet au script de trouver l'extrait même si le volume sonore est différent entre les deux fichiers.
3. Analyse FFT : Plutôt que de comparer les ondes point par point (ce qui prendrait des heures), le script transforme les sons en données fréquentielles. Il fait "glisser" virtuellement l'extrait sur l'émission complète pour trouver le moment exact où les deux signaux se superposent parfaitement.
4. Localisation du Pic : Le point de corrélation le plus élevé indique le début de l'extrait dans l'émission.

## Avantages

* Precision : Précis à la milliseconde près.
* Rapidite : L'utilisation de la FFT (Convolution) permet d'analyser une émission de 2 heures en quelques secondes.
* Robustesse : Fonctionne même si l'extrait a été légèrement compressé ou si le volume a été modifié.
