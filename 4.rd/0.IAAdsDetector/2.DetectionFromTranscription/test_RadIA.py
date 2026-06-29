#!/usr/bin/env python3
import re
from transformers import pipeline
import numpy as np


def parse_srt_file(srt_path):
    """
    Parse un fichier SRT et retourne une liste de segments avec timestamps et texte
    """
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    segments = []
    # Pattern pour parser le format SRT: numéro -> timestamp -> texte -> ligne vide
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n$)'

    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        num, start_time, end_time, text = match
        # Convertir les timestamps en secondes
        start_seconds = timestamp_to_seconds(start_time)
        end_seconds = timestamp_to_seconds(end_time)
        # Nettoyer le texte (retour chariot, espaces multiples)
        text = ' '.join(text.replace('\n', ' ').split())

        segments.append({
            'index': int(num),
            'start': start_seconds,
            'end': end_seconds,
            'text': text
        })

    return segments


def timestamp_to_seconds(timestamp):
    """
    Convertit un timestamp HH:MM:SS,mmm en secondes
    """
    timestamp = timestamp.replace(',', '.')
    parts = timestamp.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    else:
        return float(parts[0])


def detect_ads_from_srt(srt_path, threshold=0.5):
    """
    Détecte les publicités dans un fichier SRT
    """
    print(f"📖 Lecture du fichier SRT: {srt_path}")
    segments = parse_srt_file(srt_path)
    print(f"✅ {len(segments)} segments trouvés\n")

    print("🤖 Chargement du modèle de classification...")
    # Utiliser un pipeline de classification de texte standard
    classifier = pipeline(
        "text-classification",
        model="roberta-base",
        top_k=None  # Récupère tous les scores
    )

    print("🔍 Analyse des segments...\n")

    ad_segments = []

    for i, segment in enumerate(segments[:50]):  # Limiter aux 50 premiers segments pour le test
        text = segment['text']
        if len(text.strip()) < 10:  # Ignorer les segments trop courts
            continue

        # Afficher la progression
        if i % 10 == 0:
            print(f"   Analyse du segment {i + 1}/{len(segments[:50])}...")

        try:
            # Classifier le texte
            result = classifier(text[:512])  # Limiter à 512 tokens

            # Le résultat est une liste de dictionnaires
            if result and isinstance(result, list):
                # Chercher le score pour LABEL_1 (généralement la classe positive)
                ad_score = 0
                for item in result[0]:
                    if item['label'] == 'LABEL_1':
                        ad_score = item['score']
                        break

                # Si pas de LABEL_1, prendre le score le plus élevé (à ajuster)
                if ad_score == 0 and result[0]:
                    ad_score = result[0][0]['score']

                if ad_score > threshold:
                    ad_segments.append({
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': text[:200],
                        'confidence': ad_score
                    })

                    print(f"   🎯 PUBLICITÉ détectée à {format_time(segment['start'])}")
        except Exception as e:
            print(f"   ⚠️ Erreur sur segment {i + 1}: {e}")
            continue

    # Regrouper les segments adjacents
    if ad_segments:
        grouped_ads = group_adjacent_segments(ad_segments, gap_threshold=2.0)

        print(f"\n📊 RÉSULTATS DE LA DÉTECTION")
        print(f"   Segments publicitaires: {len(ad_segments)}")
        print(f"   Blocs publicitaires: {len(grouped_ads)}")
        print()

        for i, ad in enumerate(grouped_ads):
            duration = ad['end'] - ad['start']
            print(f"📢 BLOC PUBLICITAIRE #{i + 1}")
            print(f"   De {format_time(ad['start'])} à {format_time(ad['end'])} (durée: {duration:.1f}s)")
            print()

        return grouped_ads
    else:
        print("❌ Aucune publicité détectée avec le seuil actuel.")
        print("   Essayez d'abaisser le seuil avec threshold=0.3")
        return []


def group_adjacent_segments(segments, gap_threshold=2.0):
    """
    Regroupe les segments publicitaires adjacents
    """
    if not segments:
        return []

    grouped = []
    current_group = {
        'start': segments[0]['start'],
        'end': segments[0]['end'],
        'confidences': [segments[0]['confidence']]
    }

    for seg in segments[1:]:
        if seg['start'] - current_group['end'] <= gap_threshold:
            # Adjacent ou proche
            current_group['end'] = max(current_group['end'], seg['end'])
            current_group['confidences'].append(seg['confidence'])
        else:
            # Nouveau groupe
            grouped.append({
                'start': current_group['start'],
                'end': current_group['end'],
                'avg_confidence': np.mean(current_group['confidences']),
                'segment_count': len(current_group['confidences'])
            })
            current_group = {
                'start': seg['start'],
                'end': seg['end'],
                'confidences': [seg['confidence']]
            }

    # Ajouter le dernier groupe
    grouped.append({
        'start': current_group['start'],
        'end': current_group['end'],
        'avg_confidence': np.mean(current_group['confidences']),
        'segment_count': len(current_group['confidences'])
    })

    return grouped


def format_time(seconds):
    """
    Formate les secondes en HH:MM:SS
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def detect_ads_with_keywords(srt_path):
    """
    Version alternative basée sur des mots-clés (plus rapide, sans modèle)
    """
    print("🔍 Détection par mots-clés...")

    # Mots-clés typiques des publicités françaises
    ad_keywords = [
        "promotion", "offre spéciale", "exclusive", "gratuit", "abonnement",
        "cliquez", "téléchargez", "inscrivez", "code promo", "réduction",
        "livraison offerte", "premier mois offert", "sans engagement",
        "profitez", "découvrez", "nouveau", "limitée", "jusqu'au",
        "commandez", "visitez", "rendez-vous sur", "site web",
        "facebook", "instagram", "abonnez-vous", "likez", "partagez"
    ]

    segments = parse_srt_file(srt_path)
    ad_segments = []

    for segment in segments:
        text = segment['text'].lower()

        # Compter les mots-clés
        keyword_count = sum(1 for keyword in ad_keywords if keyword in text)
        score = min(keyword_count / 3, 1.0)  # Normaliser

        if score > 0.3:  # Au moins un mot-clé pertinent
            ad_segments.append({
                'start': segment['start'],
                'end': segment['end'],
                'confidence': score,
                'keywords_found': keyword_count
            })

    grouped = group_adjacent_segments(ad_segments)

    print(f"📊 {len(grouped)} blocs publicitaires détectés")
    for i, ad in enumerate(grouped):
        duration = ad['end'] - ad['start']
        print(f"   #{i + 1}: {format_time(ad['start'])} -> {format_time(ad['end'])} ({duration:.0f}s)")

    return grouped


# ============================================
# UTILISATION
# ============================================

if __name__ == "__main__":
    srt_file = "10241-01.12.2025-ITEMA_24328152-2025F10761S0335-NET_MFI_9428D60B-C293-49F7-9A16-1289E7C0CC0D-22-525c32bf42fbeb1c5500fbe2a353095f_transcription.srt"

    print("=" * 60)
    print("DÉTECTION DE PUBLICITÉS RADIO")
    print("=" * 60)
    print()

    # Option 1: Avec modèle IA (plus précis mais plus lent)
    print("Option 1: Détection par IA")
    print("-" * 40)
    # detected_ads = detect_ads_from_srt(srt_file, threshold=0.5)

    # Option 2: Avec mots-clés (plus rapide, bonne première approximation)
    print("\nOption 2: Détection par mots-clés")
    print("-" * 40)
    detected_ads = detect_ads_with_keywords(srt_file)

    if detected_ads:
        print("\n✂️  Commandes pour extraire les publicités (avec ffmpeg):")
        for i, ad in enumerate(detected_ads):
            print(
                f"   ffmpeg -i audio_original.m4a -ss {format_time(ad['start'])} -to {format_time(ad['end'])} -c copy pub_{i + 1}.m4a")