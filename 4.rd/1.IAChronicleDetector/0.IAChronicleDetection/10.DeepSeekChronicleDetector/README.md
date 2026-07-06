Pour extraire les chroniques le plus vite possible :
```
python src/live_audio_detect.py --audio "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/3.modelEvaluationData/france-inter/audio/27-05-2026.m4a" --output "resultats_inter.json"
```

Pour tester la détection sur une transcription existante ou simuler un flux temps réel :
```
python src/main.py --audio "/Users/eglantine/Dev/0.perso/2.Proutechos/9.GroovyMorning/4.rd/@assets/3.modelEvaluationData/france-inter/audio/27-05-2026.m4a" --output "resultats_inter.json" --date 2026-05-27Est
```