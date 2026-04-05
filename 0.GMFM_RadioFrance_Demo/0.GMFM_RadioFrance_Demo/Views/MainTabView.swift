//
//  MainTabView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct MainTabView: View {
    @State private var selectedTab = 0
    @ObservedObject var playbackManager = PlaybackManager.shared
    @State private var isSimulatorMode = APIService.shared.isSimulatorMode
    
    var body: some View {
        ZStack(alignment: .topTrailing) {
            TabView(selection: $selectedTab) {
                HomeView()
                    .tabItem {
                        Label("Accueil", systemImage: "house.fill")
                    }
                    .tag(0)
                
                Text("Musique")
                    .tabItem {
                        Label("Musique", systemImage: "music.note")
                    }
                    .tag(1)
                
                LiveView()
                    .tabItem {
                        Label("Directs", systemImage: "antenna.radiowaves.left.and.right")
                    }
                    .tag(2)
                
                Text("Recherche")
                    .tabItem {
                        Label("Recherche", systemImage: "magnifyingglass")
                    }
                    .tag(3)
                
                Text("Bibliothèque")
                    .tabItem {
                        Label("Bibliothèque", systemImage: "person.crop.circle")
                    }
                    .tag(4)
            }
            .accentColor(.white)
            .preferredColorScheme(.dark)
            .fullScreenCover(isPresented: $playbackManager.showFullPlayer) {
                PlayerView(playerManager: playbackManager.audioPlayerManager)
            }
            
            // Simulator Mode Toggle
            HStack(spacing: 8) {
                Text("Simu")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(.white.opacity(0.6))
                
                Toggle("", isOn: $isSimulatorMode)
                    .toggleStyle(SwitchToggleStyle(tint: .blue))
                    .labelsHidden()
                    .scaleEffect(0.7)
                    .onChange(of: isSimulatorMode) { newValue in
                        APIService.shared.isSimulatorMode = newValue
                        // Optional: Reset player setup when mode changes
                        Task {
                            try? await playbackManager.audioPlayerManager.setup()
                        }
                    }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Color.black.opacity(0.5))
            .clipShape(Capsule())
            .padding(.trailing, 10)
            .padding(.top, 50) // Adjust based on dynamic island/notch
            .zIndex(100)
        }
    }
}
