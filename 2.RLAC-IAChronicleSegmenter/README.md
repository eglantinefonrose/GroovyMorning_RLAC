À lancer **dans l'ordre suivant** dans des terminaux séparés

### Lancer le serveur API
```
python3 api-server.py
```

### Lancer le segmenteur
```
SIMU=True python src/live_radio_segmenter.py
```

### Lancer le flux via ffmpeg
```
ffmpeg -re -i "assets/transitions_chroniques_à_la_suite.m4a" -f s16le -ac 1 -ar 16000 -y /tmp/audio_pipe
```

Si on veut utiliser le workflow avec le serveur Java, lancer d'abord le serveur Java puis les commandes ci dessus