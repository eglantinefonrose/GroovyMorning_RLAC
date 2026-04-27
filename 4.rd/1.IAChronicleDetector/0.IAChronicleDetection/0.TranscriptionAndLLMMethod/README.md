# Méthode : Transcription + LLM (Prompt Engineering)

Cette approche repose sur l'intelligence sémantique des modèles de langage (LLM) pour identifier les chroniques à partir du texte transcrit.

## Détails Techniques

L'approche utilise une technique de **Few-Shot Prompting** (apprentissage par l'exemple) :
1.  **Extraction de données** : Le script `main.py` charge plusieurs transcriptions au format SRT qui servent de "vérité terrain" (ground truth).
2.  **Construction du Prompt** : On construit un prompt massif qui contient :
    *   La transcription du fichier à analyser.
    *   Une série d'exemples d'émissions passées avec leurs transcriptions complètes et les timecodes exacts de leurs chroniques.
3.  **Inférence** : Le modèle (par défaut `mistral` via Ollama) analyse ces exemples pour comprendre la structure récurrente de l'émission (jingles, introductions, transitions) et applique cette logique au nouveau fichier pour extraire les noms des chroniques et leurs timecodes.

## Observations et Résultats

*   **Performance des modèles** : Les tests montrent que les modèles locaux légers (7B-13B paramètres) peinent parfois à maintenir la cohérence sur de très longs contextes. Les modèles plus puissants (via API en ligne comme GPT-4) obtiennent d'excellents résultats, surtout si on leur fournit une liste exhaustive des chroniques habituelles de l'émission.
*   **Contexte massif** : L'approche "bourrage de prompt" consiste à donner un maximum de contexte au modèle. Bien que le résultat ne soit pas parfait (quelques erreurs sur les secondes de début/fin), la compréhension sémantique permet souvent de nommer correctement la chronique, là où les méthodes audio échouent.
*   **Limites** : Cette méthode est dépendante de la qualité de la transcription initiale et consomme beaucoup de tokens de contexte (fenêtre de contexte large indispensable).

## Utilisation

Le script utilise `ollama` pour l'inférence locale.
```bash
python main.py
```