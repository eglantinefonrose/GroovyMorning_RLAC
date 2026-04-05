//
//  LiveView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct LiveView: View {
    @ObservedObject var playbackManager = PlaybackManager.shared
    
    let stations = [
        RadioStation(name: "France Inter", color: Color(red: 0.88, green: 0, blue: 0.1), logoName: "inter", currentShow: "Simone de Beauvoir, itinéraire d'une jeune fille rangée", subtitle: "Simone de Beauvoir, itinéraire d'une jeune fille r...", hostImage: "host-simone")
    ]
    
    var body: some View {
        NavigationView {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 20) {
                    // Top Header
                    HStack {
                        Text("Directs")
                            .font(.system(size: 34, weight: .bold))
                            .foregroundColor(.white)
                        
                        if playbackManager.audioPlayerManager.isReloading {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                .padding(.leading, 8)
                        }
                        
                        Spacer()
                        
                        Button(action: {
                            // Settings logic
                        }) {
                            Image(systemName: "slider.horizontal.3")
                                .font(.system(size: 20))
                                .foregroundColor(.white)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 10)
                    
                    // Single Card centered
                    HStack {
                        Spacer()
                        if let firstStation = stations.first {
                            StationCard(station: firstStation)
                        }
                        Spacer()
                    }
                    .padding(.vertical, 40)
                }
            }
            .background(Color.black.ignoresSafeArea())
            .navigationBarHidden(true)
            .refreshable {
                try? await playbackManager.audioPlayerManager.setup()
            }
        }
        .navigationViewStyle(StackNavigationViewStyle())
    }
}

struct StationCard: View {
    let station: RadioStation
    @ObservedObject var playbackManager = PlaybackManager.shared
    
    var body: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .topTrailing) {
                RoundedRectangle(cornerRadius: 32)
                    .fill(station.color)
                    .frame(width: 320, height: 480)
                
                // Station Logo
                Image(systemName: "radio") // Placeholder
                    .font(.system(size: 24))
                    .foregroundColor(.white)
                    .padding(24)
                
                VStack(spacing: 24) {
                    Spacer()
                    
                    // Host Image (Circular)
                    ZStack {
                        Circle()
                            .stroke(Color.white.opacity(0.4), lineWidth: 4)
                            .frame(width: 220, height: 220)
                        
                        Circle()
                            .fill(Color.white.opacity(0.1))
                            .frame(width: 200, height: 200)
                            .overlay(
                                Image(systemName: "person.fill")
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 100)
                                    .foregroundColor(.white.opacity(0.8))
                            )
                    }
                    
                    // Show Info
                    VStack(spacing: 8) {
                        Text(playbackManager.audioPlayerManager.currentChronicleName ?? playbackManager.audioPlayerManager.programs.first?.title ?? station.currentShow)
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .padding(.horizontal, 20)
                        
                        // Subtitle removed as requested
                    }
                    
                    // Main Play/Pause Button
                    Button(action: {
                        playbackManager.playStation(station)
                    }) {
                        Text(playbackManager.currentStation?.id == station.id && playbackManager.isPlaying ? "Pause" : "Écouter")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(.black)
                            .padding(.vertical, 16)
                            .padding(.horizontal, 48)
                            .background(Color.white)
                            .clipShape(Capsule())
                    }
                    
                    // Bottom Buttons
                    HStack(spacing: 12) {
                        Button(action: {
                            // Contact logic
                        }) {
                            HStack {
                                Image(systemName: "bubble.left.fill")
                                Text("Contact")
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Color.black.opacity(0.2))
                            .foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        
                        NavigationLink(destination: ScheduleView()) {
                            HStack {
                                Image(systemName: "calendar")
                                Text("Grille")
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(Color.black.opacity(0.2))
                            .foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 24)
                }
                .frame(width: 320, height: 480)
            }
        }
    }
}

#Preview {
    LiveView()
}
