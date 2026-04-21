import ollama

# ============================================================
# CONFIGURATION
# ============================================================
MODEL = "mistral"

# ============================================================
# PROMPT
# ============================================================
fichier = open('prompt.txt', 'r', encoding='utf-8')
transcription = fichier.read()

fichier_transcription1 = open('../../@assets/transcriptions/10241-01.12.2025-ITEMA_24328152-2025F10761S0335-NET_MFI_9428D60B-C293-49F7-9A16-1289E7C0CC0D-22-525c32bf42fbeb1c5500fbe2a353095f_transcription.srt', 'r', encoding='utf-8')
transcription1 = fichier_transcription1.read()

fichier_transcription2 = open('../../@assets/transcriptions/10241-02.03.2026-ITEMA_24426247-2026F10761S0061-NET_MFI_D96242D6-6664-40AC-BC96-62ED860D8C19-22-782ae4f492230bbec83f21fb2d60d2eb.srt', 'r', encoding='utf-8')
transcription2 = fichier_transcription2.read()

fichier_transcription3 = open('../../@assets/transcriptions/10241-03.03.2026-ITEMA_24427516-2026F10761S0062-NET_MFI_0D431FBF-EB50-4A15-A70E-21F71203CB08-22-be3984edf4c44c36eb1f2680bb3e52a6_transcription.srt', 'r', encoding='utf-8')
transcription3 = fichier_transcription3.read()

fichier_transcription4 = open('../../@assets/transcriptions/10241-04.03.2026-ITEMA_24428750-2026F10761S0063-NET_MFI_2DCA107C-7FCE-4B98-AF81-F6A14522C044-22-bc4a05da55b8ce3536cef654fcdc63b4.srt', 'r', encoding='utf-8')
transcription4 = fichier_transcription4.read()

fichier_transcription5 = open('../../@assets/transcriptions/10241-05.03.2026-ITEMA_24429995-2026F10761S0064-NET_MFI_9DEEB7C5-87EA-4DBF-AA4D-C08DC6DB33DB-22-2abd27f79822dc585b2a92b5127126e0.srt', 'r', encoding='utf-8')
transcription5 = fichier_transcription5.read()

fichier_transcription8 = open('../../@assets/transcriptions/23134-10.03.2026-ITEMA_24419636-2026F10761S0069-NET_MFI_1F2D1E03-E784-414F-A983-5EF480313505-22-b2660e1543726d3a5a9adaf9de6baff6.srt', 'r', encoding='utf-8')
transcription8 = fichier_transcription8.read()

fichier_transcription6 = open('../../@assets/transcriptions/10241-11.03.2026-ITEMA_24436757-2026F10761S0070-NET_MFI_96B5E610-0692-45A4-B384-244CC42E5D7C-22-9d38d3c14d67631d041766b480f9ad82.srt', 'r', encoding='utf-8')
transcription6 = fichier_transcription6.read()

fichier_transcription7 = open('../../@assets/transcriptions/10241-12.03.2026-ITEMA_24438004-2026F10761S0071-NET_MFI_1D9FF761-D74A-4E14-AE98-E01BA206CA61-22-dc2720b231713b27ea6d0b525e8302f4.srt', 'r', encoding='utf-8')
transcription7 = fichier_transcription7.read()

fichier_transcription9 = open('../../@assets/transcriptions/23134-16.03.2026-ITEMA_24426293-2026F10761S0075-NET_MFI_27BFBB50-47FE-49D9-BD1E-D86CD736FED1-22-61570031be12cfa328f574cb355ac7b4.srt', 'r', encoding='utf-8')
transcription9 = fichier_transcription9.read()

fichier_transcription1.close()
fichier_transcription2.close()
fichier_transcription3.close()
fichier_transcription4.close()
fichier_transcription5.close()
fichier_transcription6.close()
fichier_transcription7.close()
fichier_transcription8.close()
fichier_transcription9.close()

prompt = f'''

Analyse la transcription suivante :
{transcription}

Et donne moi les différentes chroniques en indiquant les timecodes de début et de fin.
Pour chaque chronique détectée, indique :
- Le nom de la chronique
- Le timecode de début
- Le timecode de fin

Voici des exemples d'autres transcriptions d'émission avec les timecodes des chroniques pour t'aider à découper correctement l'audio.

Pour la transcription :
{transcription1}
voici les timecodes des chroniques :
13:15.000 - 17:39.000
18:36.000 - 20:16.000
20:26.000 - 23:24.000
28:23.000 - 29:31.000
30:13.000 - 42:33.000
42:35.000 - 45:04.000
45:06.000 - 48:09.000
48:09.000 - 57:15.000
57:15.000 - 60:02.000
61:24.000 - 78:34.000
78:43.000 - 79:53.000
79:53.000 - 83:10.000
83:41.000 - 108:18.200
109:20.240 - 115:12.240
115:48.240 - 119:23.240

Pour la transcription :
{transcription2}
voici les timecodes des chroniques :
01:52.840 - 12:39.560
12:42.560 - 13:56.560
15:10.560 - 00:19:03.560
00:19:07.560 - 22:00.560
22:10.560 - 26:21.960
26:55.560 - 28:24.560
29:21.560 - 41:14.560
42:06.560 - 45:10.560
45:12.560 - 48:11.560
48:18.560 - 57:08.560
57:21.560 - 59:56.560
61:11.560 - 66:24.560
76:26.560 - 78:16.560
78:24.560 - 81:32.560
82:56.560 - 105:02.560
106:38.560 - 112:32.560
112:35.560 - 115:16.560
115:22.560 - 118:51.560

Pour la transcription :
{transcription3}
voici les timecodes des chroniques :
00:00.000 - 13:14.340
13:14.500 - 14:17.620
15:18.500 - 19:15.220
19:17.460 - 22:06.860
22:15.740 - 26:33.980
27:12.340 - 29:19.700
29:27.580 - 41:31.300
42:23.660 - 45:20.420
45:23.180 - 48:17.420
48:23.980 - 57:00.220
57:15.700 - 59:43.260
59:51.580 - 75:42.540
75:43.380 - 77:25.740
77:28.700 - 80:36.220
81:27.420 - 106:42.020
107:58.540 - 113:40.500
113:40.660 - 116:22.340
116:28.340 - 119:52.540

Pour la transcription :
{transcription4}
voici les timecodes des chroniques :
00:00.000 - 13:09.680
13:09.680 - 14:37.680
16:04.680 - 20:12.680
20:17.680 - 23:15.680
23:26.680 - 27:23.680
28:22.680 - 29:45.680
29:51.680 - 41:56.680
42:52.680 - 46:06.680
46:07.680 - 48:59.680
49:03.680 - 57:24.680
57:41.680 - 60:28.680
60:32.680 - 75:38.680
75:38.680 - 77:16.680
77:22.680 - 80:35.680
81:22.680 - 104:57.560
106:49.640 - 112:57.440
113:00.120 - 116:15.240
116:20.960 - 120:17.000

Pour la transcription :
{transcription5}
voici les timecodes des chroniques :
00:00.000 - 13:02.000
13:02.000 - 14:12.000
15:19.000 - 19:30.000
19:34.000 - 22:20.000
22:30.000 - 26:34.000
27:31.000 - 28:56.000
29:36.000 - 41:48.000
42:39.000 - 45:33.000
45:33.000 - 48:26.000
48:33.000 - 57:31.000
57:40.000 - 59:41.000
59:52.000 - 75:28.000
75:31.000 - 77:19.000
77:32.000 - 80:42.000
82:25.000 - 106:29.000
108:08.000 - 113:43.000
113:43.000 - 116:24.000
116:32.000 - 119:56.000

Pour la transcription :
{transcription6}
voici les timecodes des chroniques :
00:00.000 - 13:14.800
13:19.800 - 14:59.800
16:10.800 - 20:09.800
20:16.800 - 22:43.800
22:49.800 - 26:41.800
27:46.800 - 29:15.800
29:22.800 - 41:38.800
42:38.800 - 00:45:54.800
45:54.800 - 00:48:46.800
48:53.800 - 00:58:12.800
58:17.800 - 01:00:52.800
61:02.800 - 76:31.800
76:31.800 - 78:18.800
78:25.800 - 81:34.360
82:33.880 - 107:02.880
108:33.880 - 114:27.880
114:27.880 - 117:20.880
117:22.880 - 120:45.880

Pour la transcription :
{transcription7}
voici les timecodes des chroniques :
00:00.000 - 13:31.000
13:31.000 - 15:19.000
17:10.000 - 21:12.000
21:17.000 - 23:58.000
24:04.000 - 27:51.720
28:48.720 - 30:13.720
30:17.720 - 42:25.720
43:08.720 - 46:00.720
46:00.720 - 49:08.720
49:14.720 - 57:58.720
57:58.720 - 60:27.680
60:33.680 - 66:39.060
66:39.060 - 68:33.340
68:36.340 - 71:51.340
73:09.340 - 105:32.340
107:33.340 - 113:48.340
113:48.340 - 116:52.340
116:57.340 - 120:56.300

Pour la transcription :
{transcription8}
voici les timecodes des chroniques :
00:00.000 - 13:15.560
13:15.560 - 15:29.560
17:03.560 - 20:49.560
20:53.560 - 23:19.560
23:26.560 - 27:03.560
28:35.560 - 29:54.560
29:59.560 - 42:03.560
43:09.560 - 46:08.560
46:08.560 - 49:10.560
49:12.560 - 57:50.560
57:54.560 - 60:23.200
60:24.560 - 66:53.600
66:53.600 - 68:45.480
68:45.800 - 72:01.960
73:14.360 - 105:17.360
107:07.360 - 112:36.360
112:36.360 - 115:32.360
115:34.360 - 119:21.900

Pour la transcription :
{transcription9}
voici les timecodes des chroniques :
00:00,000 --> 14:08,200
15:41,200 --> 21:30,200
21:34,200 --> 24:01,200
24:08,200 --> 27:41,300
28:50,300 --> 30:01,300
30:07,300 --> 42:18,300
43:03,300 --> 46:08,300
46:09,300 --> 49:03,300
49:07,300 --> 57:58,300
58:02,300 --> 61:10,300
61:16,300 --> 77:55,300
77:55,300 --> 79:37,300
79:42,300 --> 82:52,300
84:32,300 --> 95:47,300
95:57,300 --> 108:03,300
108:57,300 --> 119:22,300
'''



# ============================================================
# APPEL AU MODÈLE
# ============================================================
def detect_chroniques():
    print("=" * 60)
    print(f"  Modèle utilisé : {MODEL}")
    print("\n🔍 Détection des chroniques en cours...\n")

    # Stream la réponse token par token dans la console
    stream = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    print("📺 Résultat :\n")
    for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)

    print("\n\n" + "=" * 60)
    print("  Analyse terminée !")
    print("=" * 60)


if __name__ == "__main__":
    detect_chroniques()