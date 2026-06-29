import re
import sys
import os
from datetime import timedelta
from typing import List, Tuple, Optional


class Timecode:
    """Gestion des timecodes au format HH:MM:SS.ms"""

    def __init__(self, timecode_str: str):
        self.timecode_str = timecode_str
        self.total_seconds = self._to_seconds(timecode_str)

    def _to_seconds(self, timecode: str) -> float:
        """Convertit un timecode en secondes"""
        # Format: HH:MM:SS.ms
        match = re.match(r'(\d{2}):(\d{2}):(\d{2})\.(\d+)', timecode)
        if match:
            hours, minutes, seconds, ms = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(ms) / 1000
        raise ValueError(f"Format de timecode invalide: {timecode}")

    def __sub__(self, other):
        return self.total_seconds - other.total_seconds

    def __add__(self, seconds: float):
        new_time = self.total_seconds + seconds
        return Timecode.from_seconds(new_time)

    @classmethod
    def from_seconds(cls, seconds: float):
        """Crée un Timecode à partir de secondes"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return cls(f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}")

    def __str__(self):
        return self.timecode_str


class Chronique:
    """Représente une chronique avec son timecode de début et fin"""

    def __init__(self, debut: Timecode, fin: Timecode, nom_fichier: str):
        self.debut = debut
        self.fin = fin
        self.nom_fichier = nom_fichier
        self.decalage = 0  # Décalage à appliquer

    def duree(self) -> float:
        """Durée de la chronique en secondes"""
        return self.fin.total_seconds - self.debut.total_seconds


class SousTitre:
    """Représente un sous-titre avec son timecode"""

    def __init__(self, debut: Timecode, fin: Timecode, texte: str):
        self.debut = debut
        self.fin = fin
        self.texte = texte


def lire_chroniques(fichier_chroniques: str) -> List[Chronique]:
    """Lit le fichier des chroniques"""
    chroniques = []
    with open(fichier_chroniques, 'r', encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            # Format: [HH:MM:SS.ms] - [HH:MM:SS.ms] nom_fichier.mp3
            match = re.match(r'\[([^\]]+)\]\s*-\s*\[([^\]]+)\]\s+(.+)', ligne)
            if match:
                debut, fin, nom_fichier = match.groups()
                chroniques.append(Chronique(Timecode(debut), Timecode(fin), nom_fichier))
    return chroniques


def lire_sous_titres(fichier_srt: str) -> List[SousTitre]:
    """Lit un fichier de sous-titres au format [HH:MM:SS.ms --> HH:MM:SS.ms] texte"""
    sous_titres = []

    with open(fichier_srt, 'r', encoding='utf-8') as f:
        for num_ligne, ligne in enumerate(f, 1):
            ligne = ligne.strip()
            if not ligne:
                continue

            # Chercher le premier crochet
            debut1 = ligne.find('[')
            if debut1 == -1:
                continue

            # Chercher le séparateur --> à l'intérieur des crochets
            fleche = ligne.find('-->', debut1)
            if fleche == -1:
                continue

            # Chercher le crochet fermant après le -->
            fin1 = ligne.find(']', fleche)
            if fin1 == -1:
                continue

            # Extraire les timecodes (ils sont à l'intérieur du même crochet)
            timecodes = ligne[debut1 + 1:fin1].split('-->')
            if len(timecodes) != 2:
                continue

            timecode1 = timecodes[0].strip()
            timecode2 = timecodes[1].strip()

            # Extraire le texte (tout ce qui reste après le crochet fermant)
            texte = ligne[fin1 + 1:].strip()

            if texte and timecode1 and timecode2:
                try:
                    sous_titres.append(SousTitre(Timecode(timecode1), Timecode(timecode2), texte))
                    if len(sous_titres) <= 5:
                        print(f"  ✓ Ligne {num_ligne}: {timecode1} --> {timecode2}")
                except ValueError as e:
                    if len(sous_titres) <= 5:
                        print(f"  ✗ Ligne {num_ligne}: Erreur - {e}")

    print(f"  → {len(sous_titres)} sous-titres trouvés")
    return sous_titres


def ecrire_sous_titres(sous_titres: List[SousTitre], fichier_sortie: str):
    """Écrit les sous-titres dans un fichier SRT"""
    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        for i, st in enumerate(sous_titres, 1):
            debut = str(st.debut).replace('.', ',')
            fin = str(st.fin).replace('.', ',')
            f.write(f"{i}\n{debut} --> {fin}\n{st.texte}\n\n")


def ecrire_chroniques(chroniques: List[Chronique], fichier_sortie: str):
    """Écrit les chroniques dans un fichier"""
    with open(fichier_sortie, 'w', encoding='utf-8') as f:
        for chronique in chroniques:
            f.write(f"[{chronique.debut}] - [{chronique.fin}] {chronique.nom_fichier}\n")


def traiter_fichiers(fichier_chroniques: str, fichier_srt: str):
    """Fonction principale de traitement"""

    print(f"Lecture du fichier des chroniques: {fichier_chroniques}")
    chroniques = lire_chroniques(fichier_chroniques)
    print(f"  → {len(chroniques)} chroniques trouvées")

    print(f"Lecture du fichier des sous-titres: {fichier_srt}")
    sous_titres = lire_sous_titres(fichier_srt)
    print(f"  → {len(sous_titres)} sous-titres trouvés")

    # Filtrer les sous-titres qui sont dans les chroniques
    sous_titres_filtres = []
    decalage_cumule = 0
    temps_derniere_chronique = None

    for i, chronique in enumerate(chroniques):
        # Calculer le décalage à appliquer à cette chronique
        if temps_derniere_chronique is not None:
            ecart = chronique.debut.total_seconds - temps_derniere_chronique
            if ecart > 120:  # Plus de 2 minutes (120 secondes)
                print(
                    f"  → Écart de {ecart:.1f} secondes entre chronique {i} et {i + 1}, suppression des sous-titres entre les deux")
                # On ajoute l'écart au décalage cumulé, mais on ne l'applique pas à cette chronique
                # car on supprime ce temps
                decalage_cumule += ecart
            else:
                # Garder l'écart normal
                decalage_cumule += ecart

        # Appliquer le décalage à cette chronique
        nouveau_debut = Timecode.from_seconds(chronique.debut.total_seconds - decalage_cumule)
        nouvelle_fin = Timecode.from_seconds(chronique.fin.total_seconds - decalage_cumule)

        # Mettre à jour la chronique avec les nouveaux timecodes
        chronique.debut = nouveau_debut
        chronique.fin = nouvelle_fin
        chronique.decalage = decalage_cumule

        # Récupérer les sous-titres de cette chronique
        debut_original = chronique.debut.total_seconds + decalage_cumule
        fin_original = chronique.fin.total_seconds + decalage_cumule

        for st in sous_titres:
            if (st.debut.total_seconds >= debut_original and
                    st.fin.total_seconds <= fin_original):
                # Appliquer le décalage à ce sous-titre
                nouveau_st_debut = Timecode.from_seconds(st.debut.total_seconds - decalage_cumule)
                nouveau_st_fin = Timecode.from_seconds(st.fin.total_seconds - decalage_cumule)
                sous_titres_filtres.append(SousTitre(nouveau_st_debut, nouveau_st_fin, st.texte))

        temps_derniere_chronique = fin_original

    # Générer les noms des fichiers de sortie
    base_srt = os.path.splitext(fichier_srt)[0]
    fichier_srt_new = f"{base_srt}_new.srt"

    base_chroniques = os.path.splitext(fichier_chroniques)[0]
    fichier_chroniques_new = f"{base_chroniques}_new.txt"

    print(f"\nÉcriture des nouveaux sous-titres: {fichier_srt_new}")
    ecrire_sous_titres(sous_titres_filtres, fichier_srt_new)
    print(f"  → {len(sous_titres_filtres)} sous-titres sauvegardés")

    print(f"Écriture des nouvelles chroniques: {fichier_chroniques_new}")
    ecrire_chroniques(chroniques, fichier_chroniques_new)
    print("  → Terminé !")


def main():
    if len(sys.argv) != 3:
        print("Usage: python update_subtitles_and_chronique_files.py timecode_chroniques/1.rtl-matin/timecode_chroniques_06-04-2026.txt ../../../1.modelOutputs/0.transcriptions/1.transcriptions_whisper_ggml-large-v3-turbo/2.rtl-matin/06-04/06-04-26_transcription.srt")
        print("Exemple: python script.py chroniques.txt subtitles.srt")
        sys.exit(1)

    fichier_chroniques = sys.argv[1]
    fichier_srt = sys.argv[2]

    if not os.path.exists(fichier_chroniques):
        print(f"Erreur: Le fichier {fichier_chroniques} n'existe pas")
        sys.exit(1)

    if not os.path.exists(fichier_srt):
        print(f"Erreur: Le fichier {fichier_srt} n'existe pas")
        sys.exit(1)

    try:
        traiter_fichiers(fichier_chroniques, fichier_srt)
    except Exception as e:
        print(f"Erreur lors du traitement: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()