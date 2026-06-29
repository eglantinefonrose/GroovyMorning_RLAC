Prends les transcriptions qui sont dans le dossier 0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo et détecte les chroniques pour chaque transcription.
Voici l'ordre des chroniques et leurs horaires supposées :
[
  {
    "time": "07h00",
    "title": "Le journal de 7h"
  },
  {
    "time": "07h13",
    "title": "Les 80''"
  },
  {
    "time": "07h16",
    "title": "Le Grand reportage de France Inter"
  },
  {
    "time": "07h20",
    "title": "L'édito médias"
  },
  {
    "time": "07h23",
    "title": "Musicaline"
  },
  {
    "time": "07h28",
    "title": "La météo"
  },
  {
    "time": "07h30",
    "title": "Le journal de 7h30"
  },
  {
    "time": "07h43",
    "title": "L'édito politique"
  },
  {
    "time": "07h46",
    "title": "L'édito éco"
  },
  {
    "time": "07h49",
    "title": "L'invité de 7h50"
  },
  {
    "time": "07h56",
    "title": "Le billet de Bertrand Chameroy"
  },
  {
    "time": "08h00",
    "title": "Le journal de 8h"
  },
  {
    "time": "08h17",
    "title": "Géopolitique"
  },
  {
    "time": "08h21",
    "title": "L'invité de 8h20 : le grand entretien"
  },
  {
    "time": "08h46",
    "title": "Dans l'œil de"
  },
  {
    "time": "08h52",
    "title": "Un monde nouveau"
  },
  {
    "time": "08h54",
    "title": ""
  }
]
Pour la dernière chronique (8h54), si on est le premier jour d'une série consécutive de 4 jours, alors l'émission est "Merci Véro", le deuxième jour l'émission est "Dans la bouche de Sofia Aram", le 3ème jour "Le billet de Mosimann", et le 4ème jour "La question de David Castello-Lopes".

Je voudrais que tu écrives les chroniques détectées dans un fichier texte nommé du nom de la transcription auquel tu rajoutes le suffixe _chronique et de type txt.
Par exemple si tu analyses le fichier "fff_transcription.srt", alors les chroniques doivent être dans le fichier "fff_transcription_chronique.txt".

Les chroniques doivent être au format :
[HH:MM:SS.MSMSMS] - [HH:MM:SS.MSMSMS] Nom de la chronique - Chroniqueur/chroniqueuse

Écris ces chroniques dans le dossier "1.timecode-segments/1.geminiCLI/2.gemini-flash-avec-vrais-horaires-théoriques/1.round2".