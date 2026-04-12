Est-ce que tu peux regarder le contenu du projet `./2.MachineLearningTranscription` et me dire en quoi les deux modèles présents dans `./2.MachineLearningTranscription/models` se distinguent ?

---

Dans le fichier README.md du projet `./2.MachineLearningTranscription`, on veut rajouter :
 - expliquer clairement ce que tu as 
 - une section `Comment tester le modèle`
 - une section `Publication du modèle sur Hugging Face` dans le fichier README.md.
sur le même principe que ce qu'on a fait dans `./1.MachineLearningAudio/README.md`.

Le nom du modèle de ce projet est `rlac-audiotranscription-segmenter-chroniques_model`.

J'ai aussi créé une base de `./2.MachineLearningTranscription/models/README.md` qu'il faut compléter avec les caractéristiques du modèle (des modèles en fait) défini(s) dans ce projet.

---

Dans la section `Comment tester le modèle` du fichier `./2.MachineLearningTranscription/README.md`, tout serait très clair si on pouvait lancer l'entraînement avec `python train_model.py` et lancer l'exécution du modèle sur un fichier audio avec `python detect_chronicles.py --model models/rlac-audio-segmenter-chroniques_model.pkl chemin/vers/votre_audio.mp3`

Mets à jour le code et les parties concernées du fichier README.md existant pour que tout soit cohérent


---

Le code du projet contient plein de références à Ads ou Advertisement ou Pub (en français) car le projet a été fait à partir d'un copier/coller d'un projet qui visait à détecter des Ads/Pubs. Fais les changements de nom.