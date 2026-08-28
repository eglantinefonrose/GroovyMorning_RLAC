# RLAC - Détection des chroniques via intelligence artificielle

## Introduction
Ce document présente la méthodologie du projet RadioLiveALaCarte (RLAC), dont l'objectif est de permettre la détection et la segmentation automatique, en temps réel, des différentes chroniques au sein d'un flux radio. On utilise une chaîne de traitement complète allant de l'acquisition de données à l'inférence, en explorant plusieurs architectures d'intelligence artificielle.

### Suivi et reproductibilité des entraînements
Pour assurer une traçabilité rigoureuse de nos expérimentations, nous utilisons la plateforme Weights & Biases (WandB). Cet outil nous permet de centraliser :
- Le monitoring des métriques : suivi en temps réel de la perte (loss) et des scores de précision (F1-score) durant l'entraînement.
- La configuration matérielle : enregistrement des caractéristiques de la machine (GPU, CPU, mémoire) pour garantir la reproductibilité des résultats.
- L'archivage des hyperparamètres : conservation de chaque configuration testée pour identifier les modèles les plus performants.

### Évaluation de la performance (Scoring RLAC)
La qualité de nos modèles ne se limite pas à une simple précision statistique. Nous avons mis en place un système de notation spécifique au projet RLAC, basé sur deux critères majeurs :
- La Cardinalité (40%) : La capacité du modèle à identifier le nombre exact de chroniques présentes, sans omission ni sur-segmentation.
- L'Alignement Temporel (60%) : La précision chirurgicale des points de début et de fin de chaque chronique détectée par rapport à la réalité.

### Publication et déploiement
L'ensemble des modèles sont publiés sur l'espace Hugging Face du projet.

## Création du dataset
Pour réaliser le dataset, il faut mettre en correspondance des émissions de radio (transcription ou audio) ainsi que les timecodes des chroniques dans chaque émission.

### Données audio

#### Téléchargement manuel et étiquetage à la main

Dans un premier temps, les émissions de radio étaient téléchargés à la main depuis les différents sites web de radio et les chroniques étaient détectés à la main de manière humaine, dans un fichier texte indiquant le nom de la chronique ainsi que le timecode de début et le timecode de fin. 

#### Téléchargement manuel, étiquetage via LLM et vérification humaine
La détection des chroniques entièrement humaine a ensuite été remplacée par une détection via un LLM (gemini en cli) qui créait les fichiers texte avec les timecodes des chroniques. Une vérification humaine était ensuite appliquée via une interface Swift macOS. 

#### Téléchargement et détection automatique
La technique actuellement utilisée est 100% automatique et ne nécessite aucune intervention humaine.
- **Téléchargement des émissions** : Le téléchargement des émissions et des chroniques la composant est entièrement fait automatiquement par un programme Python. Cependant, le programme n'arrive pas à récupérer certaines chroniques, donc l'intégralité des chroniques n'est pas téléchargée.
- **Détection des chroniques** : Un second programme analyse l'audio complet et retrouve les chroniques dans cet audio pour en déduire la position des chroniques dans l'audio et créer le fichier texte qui renseigne la position des chroniques dans l'audio.
- **Ajustement du fichier texte et audio** : Comme certaines chroniques manquent, il ne faut pas les étiquetter comme 'non chronique'. Un troisième programme déduit la liste des chroniques manquantes à partir de la liste théorique des chroniques présentes dans l'émission, enlève les parties avec les chroniques manquantes de l'audio et ajuste le fichier texte en prenant en compte le nouvel audio et les chroniques manquantes.

### Données texte (transcription)
L'approche est la même pour la transcription, mais en rajoutant une étape de transcription. 

Dans un premier temps, différents de modèles de Whisper ont été testé pour utiliser finalement le modèle large-v3. Ce modèle a finalement été abandonné au profit de kyutai.   

Dans la partie **Ajustement du fichier texte et audio** de **Téléchargement et détection automatique**, les ajustements fait sur l'audio (suppression aux emplacements des chroniques manquantes) sont réalisés dans la transcription.

## Détection de chroniques à partir de la transcription des émissions de radio


Dans un premier temps, les transcriptions utilisées étaient les transcriptions du modèle large de Whisper. La méthode de génération de transcriptions a ensuite changé pour utiliser kyutai/stt-1b-en_fr.  
Les modèles suivants ont été entrainés à partir d'un dataset de transcriptions générées via le modèle de kyutai.

### Transcription et isolation des chroniques via LLM

Cette approche repose sur l'intelligence sémantique des modèles de langage (LLM) pour identifier les chroniques à partir du texte transcrit.

#### Approche Technique

L'approche utilise une technique de Few-Shot Prompting (apprentissage par l'exemple) :
1.  Extraction de données : Un script charge plusieurs transcriptions au format SRT qui servent de "vérité terrain" (ground truth).
2.  Construction du Prompt : On construit un prompt massif qui contient :
La transcription du fichier à analyser.
Une série d'exemples d'émissions passées avec leurs transcriptions complètes et les timecodes exacts de leurs chroniques.
3.  Inférence : Le modèle (par défaut `mistral` via Ollama) analyse ces exemples pour comprendre la structure récurrente de l'émission (jingles, introductions, transitions) et applique cette logique au nouveau fichier pour extraire les noms des chroniques et leurs timecodes.

#### Observations et Résultats
 Lien vers le modèle :   
 Limites : Cette méthode est dépendante de la qualité de la transcription initiale et consomme beaucoup de tokens de contexte (fenêtre de contexte large indispensable).  
Note du modèle : 

### Entrainement modèle RandomForest pour détecter les chroniques via transcription

Cette approche repose sur une méthode de détection de chroniques radio basée sur l'analyse textuelle des transcriptions (SRT) en utilisant un algorithme Random Forest.
Cette approche est légère, rapide et efficace et ne nécessite pas de GPU.

#### Approche Technique
Le modèle analyse le flux de transcription segment par segment en utilisant :

1.  Extraction de caractéristiques (Features) :
Durée des segments et métadonnées temporelles.
Statistiques textuelles (nombre de mots, ponctuation).
TF-IDF : Analyse de l'importance des mots pour identifier le vocabulaire spécifique aux chroniques.

2.  Fenêtre Glissante (Contextual Window) :
Pour chaque segment, le modèle prend en compte les caractéristiques des segments adjacents (contexte local) pour améliorer la précision de la détection.

3.  Classification :
Un classifieur Random Forest robuste qui sépare les chroniques du reste de l'émission.

#### Observations et Résultats
 Lien vers le modèle :   
 Limites :   
Note du modèle : 

### Entrainement d'un modèle hybride (Random Forest BERT fine-tuné)

Cette approche repose sur une méthode avancée de détection de chroniques radio basée sur une architecture Deep Learning Hybride analysant les transcriptions textuelles (SRT).  
Cette approche est conçue pour capturer à la fois le sens profond des paroles et la structure séquentielle d'une émission radio.

#### Approche Technique
Le modèle repose sur une architecture à trois étages :

1.  Compréhension Sémantique (CamemBERT) :
Chaque segment de texte est transformé en vecteurs de caractéristiques riches (embeddings) par le modèle de langage CamemBERT, permettant de comprendre le contexte et le sujet abordé.

2.  Modélisation Séquentielle (Bi-LSTM) :
Un réseau de neurones récurrent bidirectionnel analyse la suite des segments pour comprendre la progression de l'émission et identifier les transitions.

3.  Cohérence Temporelle (CRF) :
Une couche Conditional Random Field garantit que la séquence de labels prédite est logiquement possible (par exemple, gérer proprement le début, le milieu et la fin d'une chronique).

L'entraînement utilise une Focal Loss pour surmonter le déséquilibre des classes (les débuts de chroniques étant des événements rares).

#### Observations et Résultats
Lien vers le modèle :  
Limites :   
Note du modèle : 

### Fine-tuner le modèle sémantique BERT

Cette approche repose sur l'utilisation d'un modèle CamemBERT (BERT pour le français) pour détecter les chroniques dans les transcriptions d'émissions de radio.

#### Approche Technique
La détection de chroniques repose sur une architecture de type Transformer (CamemBERT) spécialisée dans la classification de séquences. L'approche se décompose en trois étapes majeures :  
**1. Augmentation Sémantique (Contexte)**  
Un segment de transcription isolé (souvent très court, ex: 2-3 secondes) contient rarement assez d'information pour être classé avec certitude.
Le système utilise une fenêtre glissante (par défaut 5 segments : le segment cible + 2 avant + 2 après).
Ces segments sont concaténés avec le jeton spécial [SEP].
Cela permet au modèle de capter la structure de l'émission (ex: détecter une transition, un jingle ou une annonce de sommaire).

**2. Classification Sémantique**  
Le texte contextualisé est passé dans un modèle CamemBERT (ou DistilCamemBERT) fine-tuné.
Entrée : Les tokens des 5 segments fusionnés.
Sortie : Une probabilité (0 à 1) que le segment central appartienne à une chronique.
Le modèle apprend à reconnaître non seulement le vocabulaire thématique, mais aussi les formules de politesse et les structures de discours typiques des lancements de chroniques.

**3. Post-traitement & Lissage**  
Les prédictions brutes peuvent être discontinues (ex: un segment de silence au milieu d'une chronique). Le script d'inférence applique des filtres de cohérence :
Lissage (Smoothing) : Les "trous" d'un seul segment au sein d'un bloc de détection sont automatiquement comblés.
Filtre de durée : Seuls les blocs continus de plus de 30 secondes sont conservés, éliminant ainsi les faux positifs sur des interventions brèves ou des titres.

#### Observations et Résultats
 Lien vers le modèle :  
 Limites :  
Note du modèle : 

### Fine-tuner le modèle sémantique BERT pour détecter le début d'une chronique

Cette approche utilise un modèle **CamemBERT** (via Hugging Face Transformers) pour détecter automatiquement le début des chroniques au sein de transcriptions d'émissions de radio (STT).

#### Entraînement du modèle
Le script train_camembert.py permet d'entraîner le modèle sur vos propres données.
Données : Le script récupère des fichiers .txt contenant la transcription des 10 premières secondes des chroniques et extrait la première phrase (les mots jusqu'au premier point).
Sortie : Le modèle entraîné est sauvegardé dans le dossier ./camembert_chronicle_start.

#### Inférence
Le script affiche une liste numérotée des phrases identifiées comme étant des débuts de chronique.

**Amélioration**
Au moment de l'inférence, on choisit d'afficher les 3 premières phrases de la chronique au lieu d'uniquement la première phrase de la chronique. On constate que la détection est souvent faite légèrement trop tôt.

#### Observations et Résultats
- Note du modèle : 28.2/100

**Amélioration 2**
- Gestion des Transitions : Le modèle apprend enfin à gérer le passage d'un segment à l'autre. On génère des exemples mixtes (ex: [Dernière phrase de la chronique A, Phrase de transition, Première phrase de la chronique B]) étiquetés comme début de chronique.
- Suppression du Biais de Longueur : Tous les exemples font désormais exactement 3 phrases. Le modèle ne peut plus tricher en associant "texte court" à "début de chronique".
- Élimination de la Fuite de Données : Le découpage Train/Validation se fait par Épisode complet (GroupShuffleSplit). Le modèle ne peut plus "apprendre par cœur" une transition qu'il retrouverait en validation sous une forme presque identique.
- Prise en compte de la transcription complète de l'émission pour intégrer plus de phrases "négatives" (non début de chroniques).

NB : Les entraînements ont été faits en améliorant un modèle déjà entrainé (avec les premières améliorations), un modèle n'a pas été re-généré de 0.

#### Observations et Résultats
Lien vers le modèle : 
Note du modèle : 22.4/100

### Utiliser un LLM pour détecter juste le début des chroniques
Après découverte que Claude arrive à extraire parfaitement les phrases de début de chroniques, utilisation de Qwen pour essayer d'extraire les phrases de début de chroniques.

#### Entraînement du modèle
On demande à Qwen de détecter les phrases correspond au début des chroniques. Il ne voit que les phrases au fur et à mesure (comme dans un flux live).
On utilise le few-shot prompting pour lui donner des exemples directement dans le prompt (des exemples de phrases de début de chroniques).

#### Inférence
Le script observe le flux et signale quand il détecte le début d'une chronique.

#### Observations et Résultats
Lien vers le modèle : 
Limites : 
Note du modèle : 

### Utiliser Claude pour détecter juste le début des chroniques
Après découverte que Claude arrive à extraire parfaitement les phrases de début de chroniques, utilisation de l'API de Claude pour essayer d'extraire les phrases de début de chroniques.

#### Entraînement du modèle
On appelle l'API de Claude pour détecter les phrases correspond au début des chroniques, en lui donnant la liste des chroniques à détecter (dans l'ordre). Il ne voit que les phrases au fur et à mesure (comme dans un flux live).
On utilise le few-shot prompting pour lui donner des exemples directement dans le prompt (des exemples de phrases de début de chroniques).

#### Inférence
Le script observe le flux et signale quand il détecte le début d'une chronique et son nom.

#### Observations et Résultats
Note du modèle :

### Utiliser DeepSeek pour détecter juste le début des chroniques
Pour des raisons de performances du modèle de Claude et économiques, on utilise l'API de DeepSeek pour détecter les chroniques dans le flux live.

#### Entraînement du modèle
On appelle l'API de DeepSeek (deepseek-v4-flash) pour détecter les phrases correspond au début des chroniques, en lui donnant la liste des chroniques à détecter (dans l'ordre). Il ne voit que les phrases au fur et à mesure (comme dans un flux live).
On utilise le few-shot prompting pour lui donner des exemples directement dans le prompt (des exemples de phrases de début de chroniques).

**Améliorations**
Afin d'éviter les erreurs grossières, les chroniques sont comparées avec leur horaire théorique. On ignore également une chronique détectée qui est déjà passée. 

**Inférence**
Le script observe le flux et signale quand il détecte le début d'une chronique et son nom.

**Observations et Résultats**
Note du modèle : 

## Détection de chroniques à partir des audios des émissions de radio

Après des essais non concluants en utilisant la méthode avec la transcription, une approche via la détection à partir du son uniquement a été testée.

### Machine Learning Audio

Cette approche consiste à utiliser des techniques d'apprentissage automatique (Machine Learning) en segmentant des fichiers audio longs, extrayant des caractéristiques acoustiques et entraînant un classifieur pour identifier les zones d'intérêt.

Dans cette nouvelle approche, on entraîne un modèle avec:
- des fichiers ne contenant pas de chroniques
- des fichiers qui contiennent uniquement des chroniques.

#### Approche Technique
Le modèle utilisé par défaut est un Random Forest.

#### Utilisation de Random Forest
- Efficacité : Il offre un excellent compromis entre vitesse d'entraînement et précision.
- Robustesse : Il gère bien les données de grande dimension (nombreuses caractéristiques audio).
- SVM (Support Vector Machine) : Pour une précision accrue sur de petits jeux de données.
- MLP (Multi-Layer Perceptron) : Un réseau de neurones simple pour capturer des relations complexes.

#### Caractéristiques Audio Extraites
Pour chaque segment de 3 secondes, le système extrait une signature acoustique riche :
- MFCC (Mel-Frequency Cepstral Coefficients) : Capture le timbre de la voix.
- Énergie par bande : Analyse la répartition fréquentielle.
- Zero-Crossing Rate : Détecte la présence de percussions ou de bruits.
- RMS (Root Mean Square) : Mesure l'intensité sonore.
- Caractéristiques Spectrales : Centroid, Rolloff et Bandwidth pour analyser la "brillance" du son.

#### Observations et Résultats
Lien vers le modèle :  
Limites :  
Note du modèle : 

### Finetuning de Wav2Vec2

Cette approche consiste à fine-tuner un modèle `wav2vec2-large-xlsr-53-french` pour la classification de segments audio (détection de chroniques radio) et d'effectuer des prédictions sur de nouveaux fichiers audio.

#### Approche Technique
**Entraînement**
1. Extraction des segments : Les fichiers audio sont découpés en segments selon les timecodes fournis.
2. Prétraitement : Les segments sont échantillonnés à 16 000 Hz et normalisés.
3. Fine-tuning : Utilise `Wav2Vec2ForSequenceClassification` avec une tête de classification adaptée au nombre des différentes chroniques à trouver dans l'émission.

**Prédiction**
Utilise une fenêtre glissante (par défaut 10s avec 5s d'overlap).
Prédit le label pour chaque fenêtre.
Fusionne les fenêtres consécutives ayant le même label pour produire des segments cohérents.

#### Adaptation des paramètres
Afin d'essayer de détecter correctement les chroniques, les valeurs des paramètres suivants ont été modifiés :
- Seuil de confiance (threshold) : Le seuil de confiance à partir duquel on prend en compte un résultat.
- Durée minimale : Si le modèle fragmente une chronique en plusieurs petits morceaux dont la durée est inférieure à la durée minimale non fusionnés, ils sont tous supprimés.
- Logique de fusion (Gap Filling) : Si deux segments d'une même chronique sont séparés par un court segment de "background" (bruit, jingle), ils ne sont pas fusionnés. Une logique consistant à combler les trous de moins de 3-5 secondes améliorerait grandement la robustesse. 

Même en jouant sur ces différents paramètres, aucun résultat satisfaisant lors de l'inférence n'a été obtenu.

#### Équilibrage du jeu de données
Un des soucis qui fait que les chroniques ne sont pas détectées correctement est le déséquilibre dans le jeu de données : il y a beaucoup plus de "chroniques" que de "background" dans une radio, ce qui va créer des faux positifs.

La méthode la plus précise est le levier de pourcentage. Le script génère les données, puis effectue un **sous-échantillonnage (downsampling)** automatique pour atteindre le ratio exact demandé.

- **Principe** : Si on demande 80%, le script calculera combien de segments de chaque classe garder pour que le background représente exactement 80% du total.

#### Détection binaire (chronique ou non)
Afin de simplifier et d'améliorer la détection des chroniques, on demande au modèle de détecter seulement les périodes où il y a des chroniques dans le code (sans les nommer).

#### Observations et Résultats
- Lien vers le modèle : 
- Limites : 
- Note du modèle : 

### Prédiction robuste

#### 1. Problématique Initiale  
Le script d'inférence d'origine prenait des décisions indépendantes par fenêtre de temps. Si une seule fenêtre au milieu d'une chronique obtenait un score de confiance légèrement inférieur au seuil, la chronique était coupée en deux ou ignorée.

#### 2. Améliorations Techniques
**A. Lissage par Score Compétitif (Soft Voting)**  
Au lieu de simplement prendre la probabilité de la classe "chronique", le script calcule un score pondéré :
- Si `prob_chronique > prob_background`, le score est égal à `prob_chronique`.
- Si `prob_background >= prob_chronique`, le score de chronique est divisé par deux.
Cela force le score à chuter drastiquement dès que le modèle commence à pencher vers le bruit de fond, créant ainsi des séparations nettes entre deux chroniques.

**B. Seuil à Hystérésis (Double Seuil)**  
L'utilisation d'un seuil unique crée des oscillations. Nous utilisons désormais deux seuils :
Seuil d'Activation (`threshold_start`) : Un score élevé (0.7) est nécessaire pour déclencher le début d'une chronique.
Seuil de Maintien (`threshold_end`) : Un score plus bas (0.3) suffit pour continuer la détection.

**C. Segmentation Précise**    
La fin d'un segment est désormais calculée de manière plus fine pour éviter que les chroniques ne "débordent" trop sur le silence suivant.

**D. Gestion du "Gap Filling" Intelligent**   
La fusion des segments est maintenant plus robuste car elle s'appuie sur une courbe de probabilité continue plutôt que sur des blocs de 10 secondes rigides.

#### Observations et Résultats
 Lien vers le modèle :  
 Limites :  
Note du modèle : 

### Prédiction lisse
Cette version simplifiée se concentre uniquement sur le lissage temporel par moyenne mobile pour stabiliser les détections sans utiliser la complexité de l'hystérésis ou du score compétitif.

#### Principe du Lissage (Moving Average)
Dans une prédiction classique, chaque fenêtre est traitée indépendamment. Si le modèle a une micro-hésitation, la chronique est coupée.  

L'approche lisse fonctionne ainsi :
- Elle récupère la probabilité de la classe chronique pour chaque fenêtre.
- Elle applique une moyenne glissante sur ces probabilités (au lieu de regarder la probabilité d'une fenêtre audio isolée pour décider s'il s'agit d'une chronique, on regarde la moyenne de cette fenêtre et des fenêtres qui l'entourent).
- Une décision est prise sur la valeur lissée par rapport à un seuil unique.

#### Observations et Résultats  
Lien vers le modèle :  
Limites :  
Note du modèle : 

### Approche hybride : Détection par jingles
Cette approche vise à résoudre les problèmes de précision de début de chronique en utilisant les jingles d'introduction comme points d'ancrage de haute confiance.

#### Concept
Plutôt que d'essayer de classer chaque segment de 10 secondes comme "chronique" ou "background" avec un seul modèle, ce qui crée souvent des ambiguïtés aux frontières, l'approche hybride divise le problème en deux étapes :
- Détection de Jingle : Rechercher le motif sonore court et spécifique qui annonce le début d'une chronique.
- Extension de Chronique : Une fois le début "ancré" par un jingle, utiliser le modèle de chronique général pour suivre la parole jusqu'à sa fin naturelle.

#### Entraînement du modèle de jingle
Le script d'entraînement crée un modèle binaire (Jingle vs Background) optimisé pour les signatures acoustiques. 

**Logique d'échantillonnage**

- Classe jingle (Positifs) : Le script extrait uniquement les 5 premières secondes de chaque chronique définie dans les timecodes. C'est là que se trouve généralement la signature musicale ou sonore de l'émission.
- Classe background (Négatifs) :  
  - Segments de silence ou musique entre les chroniques.
  - Segments prélevés au milieu des chroniques (après le jingle). Cela apprend au modèle à faire la distinction entre "le jingle de la chronique" et "la parole de la chronique".

#### Modèle utilisé
  Utilise AST (Audio Spectrogram Transformer) (MIT/ast-finetuned-audioset), car sa capacité à analyser l'audio comme une image (via spectrogrammes) est supérieure pour reconnaître des motifs musicaux répétitifs comme les jingles. 
  
#### Inférence Hybride
Ce script combine les deux modèles pour une segmentation précise.

#### Algorithme
1. Scan (Pas de 1s) : Le script parcourt l'audio avec le modèle de Jingle. Comme le pas est court (1s), on obtient une précision chirurgicale sur le début.
2. Détection : Si la probabilité de Jingle dépasse le seuil (ex: 0.8), un point d'ancrage est créé.
3. Suivi (Tracking) : À partir de ce point, le script bascule sur le modèle de Chronique général. Il avance par bonds de 5s pour vérifier si le contenu est toujours une chronique.
4. Fin du segment : La fin est marquée dès que le modèle de chronique renvoie une confiance faible sur une durée prolongée (15s par défaut).
5. Reprise : Le scan de jingles reprend après la fin de la chronique détectée.

#### Observations et Résultats
 Lien vers le modèle : 
 Limites : 
Note du modèle : 

### Finetuning de différents modèles

Bien que le modèle `facebook/wav2vec2-large-xlsr-53-french` soit excellent pour la reconnaissance vocale (ASR), il présente des limites pour la classification de segments :

- **Biais linguistique** : Wav2Vec2 est optimisé pour reconnaître des phonèmes et des mots. Or, une chronique se détecte souvent par sa texture sonore (jingles, musique de fond, qualité acoustique) que Wav2Vec2 peut avoir tendance à ignorer.
- **Lourdeur vs Tâche** : La version `large` (300M+ paramètres) est lourde pour une classification binaire ou multi-classes simple. Cela ralentit l'inférence et nécessite plus de données pour éviter le sur-apprentissage (overfitting).
- **Analyse Locale** : Le traitement séquentiel de l'onde brute peut manquer de vision "globale" sur un segment de 10s, notamment pour identifier des motifs musicaux complexes (jingles).

On a donc cherché à utiliser d'autres modèles pour la détection des chroniques à partir du son de l'émission.

**Inférences**
Timecodes des chroniques (sans les nommer)

**Modèle AST**    
**Description** : Convertit l'audio en spectrogramme (image) et utilise un Transformer (ViT) pour l'analyse.   
**Avantages** : Excellent pour capturer les signatures acoustiques et les jingles. C'est souvent le meilleur compromis pour la classification de scènes sonores.   
**Modèle utilisé** : `MIT/ast-finetuned-audioset-10-10-0.4593`

**Observations et Résultats**     
 Lien vers le modèle :    
 Limites :    
Note du modèle : 2.9/100


**Modèle BEATS**.   
**Description** : Un des modèles pour la classification sonore générale.   
**Avantages** : Entraîné pour capturer à la fois la parole et les sons environnementaux/musicaux. Très robuste au bruit et aux mélanges sonores.   
**Modèle utilisé** : `microsoft/beats-base`

**Observations et Résultats**.   
 Lien vers le modèle : 
 Limites : 
Note du modèle : 

Étant donné que la fonction d'inférence présente plusieurs paramètres, on utilise un programme qui prend un audio et l'emplacement réel des chroniques dans cet audio et teste toutes les combinaisons de valeur de paramètres pour obtenir ce résultat. Malheureusement, aucun modèle n'a réussi à obtenir un résultat avec les emplacements réels des chroniques.


