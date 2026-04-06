#!/usr/bin/env python3
import adetector as adt
import numpy as np
import matplotlib.pyplot as plt


def main():
    radio_stream = 'extrait_avec_pub_non_france_inter.m4a'

    print(f"Analyse du fichier : {radio_stream}")
    X = adt.core.audio2features(radio_stream)

    print("Détection des publicités...")
    prob_result = adt.core.Ad_vs_music_classifier(X)
    prob_over_time = prob_result.flatten()

    # Paramètres
    threshold = 0.90
    window = 5

    # Lissage
    kernel = np.ones(window) / window
    prob_smoothed = np.convolve(prob_over_time, kernel, mode='same')

    # Détection
    above_threshold = prob_smoothed > threshold

    # Extraction des segments
    timestamps = []
    probabilities = []

    i = 0
    while i < len(above_threshold):
        if above_threshold[i]:
            start = i
            while i < len(above_threshold) and above_threshold[i]:
                i += 1
            end = i
            timestamps.append((start * 3, end * 3))
            probabilities.append(float(np.mean(prob_smoothed[start:end])))
        else:
            i += 1

    # Affichage console
    print(f"\n--- RÉSULTATS ---")
    if len(timestamps) > 0:
        for i, (start, end) in enumerate(timestamps):
            print(f"Publicité {i + 1}: {start:.1f}s -> {end:.1f}s (confiance: {probabilities[i]:.2%})")
    else:
        print("Aucune publicité détectée")

    # Visualisation
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))

    temps = np.arange(len(prob_over_time)) * 3

    # Graphique des probabilités brutes
    ax1.plot(temps, prob_over_time, 'b-', alpha=0.5, label='Probabilité brute')
    ax1.plot(temps, prob_smoothed, 'r-', label='Probabilité lissée')
    ax1.axhline(y=threshold, color='g', linestyle='--', label=f'Seuil ({threshold})')
    ax1.fill_between(temps, 0, 1, where=above_threshold, alpha=0.3, color='red', label='Publicité détectée')
    ax1.set_ylabel('Probabilité (publicité)')
    ax1.set_xlabel('Temps (secondes)')
    ax1.set_title('Détection de publicités - Probabilités')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Histogramme des probabilités
    ax2.hist(prob_over_time, bins=20, alpha=0.7, edgecolor='black')
    ax2.axvline(x=threshold, color='r', linestyle='--', label=f'Seuil ({threshold})')
    ax2.set_xlabel('Probabilité')
    ax2.set_ylabel('Fréquence')
    ax2.set_title('Distribution des probabilités')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()