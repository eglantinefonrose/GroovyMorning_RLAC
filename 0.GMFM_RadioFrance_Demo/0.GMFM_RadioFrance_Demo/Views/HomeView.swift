//
//  HomeView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct HomeView: View {
    @State private var isLoading = true
    @State private var showSettings = false
    @State private var customIPAddress = APIService.shared.customIPAddress
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Top Header
                HStack {
                    Text("Bonjour")
                        .font(.system(size: 34, weight: .bold))
                        .foregroundColor(.white)
                    
                    Spacer()
                    
                    Button(action: {
                        showSettings = true
                    }) {
                        Image(systemName: "gearshape.fill")
                            .font(.system(size: 20))
                            .foregroundColor(.white)
                    }
                }
                .padding(.horizontal)
                .padding(.top, 10)
                
                // Featured Content Section
                if isLoading {
                    FeaturedContentSkeleton()
                } else {
                    FeaturedContentCarousel()
                }
                
                Spacer()
                    .frame(height: 100) // Padding for the mini player
            }
        }
        .background(Color.black.ignoresSafeArea())
        .sheet(isPresented: $showSettings) {
            SettingsView(isPresented: $showSettings, customIPAddress: $customIPAddress)
        }
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                withAnimation {
                    self.isLoading = false
                }
            }
        }
    }
}

struct SettingsView: View {
    @Binding var isPresented: Bool
    @Binding var customIPAddress: String
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Configuration Serveur")) {
                    HStack {
                        Text("Adresse IP")
                        Spacer()
                        TextField("http://...", text: $customIPAddress)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                    }
                    
                    Button("Réinitialiser par défaut") {
                        customIPAddress = "http://10.155.210.134:8000"
                    }
                    .foregroundColor(.red)
                }
            }
            .navigationTitle("Réglages")
            .navigationBarItems(trailing: Button("Terminer") {
                APIService.shared.customIPAddress = customIPAddress
                Task {
                    try? await PlaybackManager.shared.audioPlayerManager.setup()
                }
                isPresented = false
            })
        }
        .preferredColorScheme(.dark)
    }
}

struct FeaturedContentSkeleton: View {
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 16) {
                ForEach(0..<2) { _ in
                    RoundedRectangle(cornerRadius: 24)
                        .fill(Color.white.opacity(0.1))
                        .frame(width: 320, height: 400)
                }
            }
            .padding(.horizontal)
        }
    }
}

struct FeaturedContentCarousel: View {
    let featuredItems = [
        FeaturedContent(title: "L'ayatollah Ali Khamenei meurt dans des frappes israélo-américaines...", subtext: "L'Esprit public", duration: "58 min", color: Color(red: 0.1, green: 0.1, blue: 0.2)),
        FeaturedContent(title: "L'IA peut-elle sauver le monde ?", subtext: "France Culture", duration: "45 min", color: Color(red: 0.2, green: 0.1, blue: 0.3))
    ]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 16) {
                ForEach(featuredItems) { item in
                    ZStack(alignment: .bottomLeading) {
                        RoundedRectangle(cornerRadius: 24)
                            .fill(item.color)
                            .frame(width: 320, height: 400)
                        
                        VStack(alignment: .leading, spacing: 12) {
                            Text(item.title)
                                .font(.system(size: 24, weight: .bold))
                                .foregroundColor(.white)
                                .lineLimit(3)
                            
                            HStack {
                                Text(item.subtext)
                                    .font(.system(size: 14))
                                    .foregroundColor(.white.opacity(0.8))
                                Text("•")
                                Text(item.duration)
                                    .font(.system(size: 14))
                                    .foregroundColor(.white.opacity(0.8))
                            }
                            
                            Button(action: {
                                // Listen logic
                            }) {
                                HStack {
                                    Image(systemName: "play.fill")
                                    Text("Écouter")
                                }
                                .padding(.vertical, 12)
                                .padding(.horizontal, 24)
                                .background(Color.white.opacity(0.2))
                                .foregroundColor(.white)
                                .clipShape(Capsule())
                            }
                            .padding(.top, 8)
                        }
                        .padding(24)
                    }
                }
            }
            .padding(.horizontal)
        }
    }
}

#Preview {
    HomeView()
}
