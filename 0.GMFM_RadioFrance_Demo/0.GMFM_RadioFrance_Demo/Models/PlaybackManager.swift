//
//  PlaybackManager.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import Foundation
import SwiftUI
import Combine

@MainActor
class PlaybackManager: ObservableObject {
    @Published var currentStation: RadioStation?
    @Published var showMiniPlayer: Bool = true
    @Published var showFullPlayer: Bool = false
    
    // Integrated AudioPlayerManager logic
    let audioPlayerManager = AudioPlayerManager()
    
    static let shared = PlaybackManager()
    
    private var cancellables = Set<AnyCancellable>()
    
    var isPlaying: Bool {
        get { audioPlayerManager.isPlaying }
        set { 
            if newValue {
                audioPlayerManager.play()
            } else {
                audioPlayerManager.pause()
            }
        }
    }
    
    var progress: Double {
        let duration = audioPlayerManager.duration
        guard duration > 0 else { return 0 }
        return audioPlayerManager.currentTime / duration
    }
    
    init() {
        // Initial mock data
        self.currentStation = RadioStation(
            name: "France Inter",
            color: Color(red: 0.88, green: 0, blue: 0.1),
            logoName: "france-inter-logo",
            currentShow: "Zoom Zoom Zen",
            subtitle: "La rétro : 1976 et la naissance du RPR",
            hostImage: "zoom-zoom-zen-host"
        )
        
        // Initialize the audio player
        Task {
            do {
                try await audioPlayerManager.setup()
            } catch {
                print("Failed to setup audio player: \(error)")
            }
        }
        
        // Listen to audio player changes to update UI if needed
        audioPlayerManager.objectWillChange
            .sink { [weak self] _ in
                self?.objectWillChange.send()
            }
            .store(in: &cancellables)
    }
    
    func playStation(_ station: RadioStation) {
        self.currentStation = station
        self.showFullPlayer = true
        // In a real app, we would load the specific stream for this station
        // For now, we use the m3u8 logic already in AudioPlayerManager
        if !audioPlayerManager.isPlaying {
            audioPlayerManager.play()
        }
    }
}
