# Amélioration de la Détection de Chroniques Audio

Si le modèle actuel ne détecte aucune chronique ou produit des résultats peu concluants, voici les axes d'amélioration prioritaires, classés par impact potentiel.

## 1. Post-traitement et Seuils (Impact Immédiat)

Le script `predict.py` contient des filtres qui peuvent être trop restrictifs :

- **Seuil de confiance (`threshold`)** : Par défaut à 0.5. Si le modèle est hésitant, baissez-le à 0.3 ou 0.4 pour voir si des détections apparaissent.
- **Durée minimale** : Il existe une règle `merged = [m for m in merged if (m["end"] - m["start"]) >= 15.0]`. Si le modèle fragmente une chronique en plusieurs petits morceaux de 10s non fusionnés, ils sont tous supprimés. Essayez de réduire cette limite à 5.0 ou 10.0 secondes.
- **Logique de fusion (Gap Filling)** : Actuellement, si deux segments d'une même chronique sont séparés par un court segment de "background" (bruit, jingle), ils ne sont pas fusionnés. Une logique consistant à combler les trous de moins de 3-5 secondes améliorerait grandement la robustesse.

## 2. Qualité et Équilibre du Dataset (Entraînement)

Le problème majeur en classification audio est souvent le déséquilibre des classes :

- **Poids des classes (Class Weights)** : La classe `background` est probablement sur-représentée. Il est recommandé de modifier la fonction de perte (`loss function`) pour donner plus de poids aux chroniques rares et moins au bruit de fond.
- **Data Augmentation** : Le modèle Wav2Vec2 gagne à être exposé à des variations acoustiques durant l'entraînement :
    - Ajout de bruit blanc ou de bruits de fond variés.
    - Changement léger de pitch ou de vitesse (time stretching).
    - Gain aléatoire pour simuler des variations de volume.
- **Segments de transition** : Vérifier que les segments de début et de fin de chronique sont bien étiquetés. Un décalage de quelques secondes dans les timecodes peut polluer l'apprentissage en mélangeant jingle et parole.

## 3. Architecture et Hyperparamètres

- **Modèle de base** : `wav2vec2-large-xlsr-53-french` est optimisé pour la reconnaissance vocale. Pour la *classification* pure de séquences sonores, des modèles comme **BEATs** ou **Audio Spectrogram Transformer (AST)** sont souvent plus performants car ils analysent mieux la texture sonore globale.
- **Durée des segments** : L'entraînement se fait sur 10s. Si les jingles d'introduction sont très courts, le modèle pourrait mieux apprendre avec des segments plus granulaires (ex: 5s).
- **Unfreezing progressif** : Actuellement, le dégel de l'extracteur de caractéristiques se fait à l'époque 2. Un apprentissage plus lent (`learning_rate=1e-5`) pourrait aider à stabiliser le fine-tuning.

## 4. Stratégie de Détection (Inférence)

- **Vote Majoritaire** : Au lieu d'une seule fenêtre glissante, faire prédire le modèle sur des fenêtres de tailles différentes et moyenner les résultats.
- **Analyse spécifique du Jingle** : Souvent, une chronique est plus facile à identifier par son jingle que par le contenu parlé. Créer un détecteur spécifique de jingles (plus courts et distincts) est souvent plus fiable.

## 5. Méthodes de Debugging

Pour identifier précisément pourquoi le modèle échoue :
1. **Sortie des probabilités** : Modifier `predict.py` pour afficher les probabilités brutes de *chaque* classe sur un segment donné.
2. **Matrice de confusion** : Vérifier si le modèle ne prédit pas systématiquement `background` (signe d'un sur-apprentissage de la classe majoritaire).
