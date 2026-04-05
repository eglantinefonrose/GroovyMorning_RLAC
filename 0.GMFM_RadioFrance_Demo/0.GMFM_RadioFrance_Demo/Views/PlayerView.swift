//
//  PlayerView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct PlayerView: View {
    @ObservedObject var playerManager: AudioPlayerManager
    @Environment(\.dismiss) var dismiss
    @State private var sliderValue: Double = 0
    @State private var isDraggingSlider = false
    
    // Recording settings state
    @State private var selectedHour = 7
    @State private var selectedMinute = 0
    @State private var showRecordingSettings = false
    @State private var isSavingSettings = false
    
    // Precise colors from the image
    let cardRed = Color(red: 0.88, green: 0, blue: 0.1) // France Inter Red
    let footerDarkRed = Color(red: 0.72, green: 0, blue: 0.08) // Darker pill background
    let backgroundDim = Color.black.opacity(0.85)
    
    var body: some View {
        ZStack {
            // Background dim
            backgroundDim.ignoresSafeArea()
            
            VStack(spacing: 0) {
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        // 1. Top Logo (Slightly smaller spacing)
                        ZStack(alignment: .trailing) {
                            VStack(spacing: -2) {
                                Image(systemName: "antenna.radiowaves.left.and.right")
                                    .font(.system(size: 14))
                                Text("france")
                                    .font(.system(size: 7, weight: .bold))
                                Text("inter")
                                    .font(.system(size: 20, weight: .heavy))
                            }
                            .frame(maxWidth: .infinity)
                            
                            Button(action: { showRecordingSettings.toggle() }) {
                                Image(systemName: "clock.badge.checkmark")
                                    .font(.system(size: 20))
                                    .foregroundColor(.white)
                                    .padding(8)
                                    .background(Color.white.opacity(0.15))
                                    .clipShape(Circle())
                            }
                            .padding(.trailing, 10)
                        }
                        .foregroundColor(.white)
                        .padding(.vertical, 8)
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(cardRed)
                                .frame(width: 65, height: 65)
                        )
                        .padding(.top, 10)
                        .padding(.bottom, 15)
                        
                        // 2. Main Red Card
                        VStack(spacing: 0) {
                            // Host Image Section (Reduced to fit all screens)
                            ZStack(alignment: .topTrailing) {
                                Image(systemName: "person.fill")
                                    .resizable()
                                    .scaledToFill()
                                    .frame(width: UIScreen.main.bounds.width * 0.72, height: UIScreen.main.bounds.width * 0.72)
                                    .background(Color(red: 0.45, green: 0.35, blue: 0.85))
                                    .overlay(
                                        VStack(alignment: .leading, spacing: -2) {
                                            Spacer()
                                            Text("ZOOM ZOOM")
                                                .font(.system(size: 34, weight: .black))
                                            Text("ZEN")
                                                .font(.system(size: 34, weight: .black))
                                            Text("MATTHIEU NOËL")
                                                .font(.system(size: 16, weight: .bold))
                                                .padding(.top, 4)
                                        }
                                        .foregroundColor(.white)
                                        .padding(20),
                                        alignment: .bottomLeading
                                    )
                                    .clipShape(RoundedRectangle(cornerRadius: 16))
                                
                                VStack(spacing: -1) {
                                    Image(systemName: "antenna.radiowaves.left.and.right")
                                        .font(.system(size: 8))
                                    Text("france")
                                        .font(.system(size: 4, weight: .bold))
                                    Text("inter")
                                        .font(.system(size: 12, weight: .heavy))
                                }
                                .foregroundColor(.white)
                                .padding(5)
                                .background(cardRed)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                                .padding(10)
                            }
                            .padding(.top, 14)
                            .padding(.horizontal, 14)
                            
                            // Title and Buttons
                            HStack(alignment: .center) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(playerManager.currentChronicleName ?? "Zoom Zoom Zen")
                                        .font(.system(size: 24, weight: .bold))
                                    
                                    if let errorMessage = playerManager.errorMessage {
                                        Text(errorMessage)
                                            .font(.system(size: 11, weight: .medium))
                                            .foregroundColor(.yellow)
                                            .padding(.top, 2)
                                            .fixedSize(horizontal: false, vertical: true)
                                            .multilineTextAlignment(.leading)
                                    } else if playerManager.isLoading {
                                        Text("Chargement...")
                                            .font(.system(size: 12))
                                            .foregroundColor(.white.opacity(0.7))
                                            .padding(.top, 2)
                                    }
                                }
                                Spacer()
                                
                                HStack(spacing: 20) {
                                    Image(systemName: "plus")
                                        .font(.system(size: 22))
                                    Image(systemName: "ellipsis")
                                        .font(.system(size: 22))
                                        .rotationEffect(.degrees(90))
                                }
                            }
                            .foregroundColor(.white)
                            .padding(.horizontal, 24)
                            .padding(.top, 16)
                            
                            // Slider
                            VStack(spacing: 8) {
                                CustomSlider(value: Binding(
                                    get: { isDraggingSlider ? sliderValue : playerManager.currentTime },
                                    set: { sliderValue = $0 }
                                ), range: 0...max(playerManager.safeDuration, 1)) { editing in
                                    isDraggingSlider = editing
                                    if !editing { playerManager.seek(to: sliderValue) }
                                }
                                
                                HStack {
                                    Text(playerManager.formatTime(isDraggingSlider ? sliderValue : playerManager.currentTime))
                                        .accessibilityIdentifier("current_time_label")
                                    Spacer()
                                    Text(playerManager.formatTime(playerManager.safeDuration))
                                }
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(.white.opacity(0.8))
                            }
                            .padding(.horizontal, 24)
                            .padding(.top, 16)
                            
                            // Playback Controls
                            HStack {
                                Spacer()
                                Button(action: { playerManager.previous() }) {
                                    Image(systemName: "backward.end.fill").font(.system(size: 20))
                                }
                                Spacer()
                                Button(action: { playerManager.skipBackward() }) {
                                    Image(systemName: "gobackward.15").font(.system(size: 24))
                                }
                                .accessibilityIdentifier("gobackward.15")
                                Spacer()
                                Button(action: { playerManager.togglePlayPause() }) {
                                    ZStack {
                                        Circle().fill(Color.white).frame(width: 70, height: 70)
                                        Image(systemName: playerManager.isPlaying ? "pause.fill" : "play.fill")
                                            .font(.system(size: 32))
                                            .foregroundColor(cardRed)
                                            .offset(x: playerManager.isPlaying ? 0 : 3)
                                    }
                                }
                                Spacer()
                                Button(action: { playerManager.skipForward() }) {
                                    Image(systemName: "goforward.30").font(.system(size: 24))
                                }
                                .accessibilityIdentifier("goforward.30")
                                Spacer()
                                Button(action: { playerManager.next() }) {
                                    Image(systemName: "forward.end.fill").font(.system(size: 20))
                                }
                                Spacer()
                            }
                            .foregroundColor(.white)
                            .padding(.top, 15)
                            .padding(.bottom, 20)
                            
                            // Tool Pill
                            HStack {
                                Spacer()
                                HStack(spacing: 4) {
                                    Image(systemName: "zzz").font(.system(size: 12))
                                    Text("zZz").font(.system(size: 12, weight: .bold))
                                }
                                Spacer()
                                Text("x1").font(.system(size: 14, weight: .bold))
                                Spacer()
                                Image(systemName: "speaker.wave.2.fill").font(.system(size: 16))
                                Spacer()
                                Image(systemName: "list.bullet.below.rectangle").font(.system(size: 16))
                                Spacer()
                            }
                            .foregroundColor(.white)
                            .padding(.vertical, 14)
                            .background(footerDarkRed)
                            .clipShape(Capsule())
                            .padding(.horizontal, 16)
                            .padding(.bottom, 16)
                        }
                        .background(cardRed)
                        .clipShape(RoundedRectangle(cornerRadius: 40, style: .continuous))
                        .padding(.horizontal, 15)
                        
                        // Chronicles List
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text("Chroniques du jour")
                                    .font(.headline)
                                    .foregroundColor(.white)
                                
                                if playerManager.isReloading {
                                    ProgressView()
                                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                        .scaleEffect(0.8)
                                }
                            }
                            .padding(.horizontal, 24)
                            .padding(.top, 10)
                            
                            VStack(spacing: 8) {
                                ForEach(0..<playerManager.programs.count, id: \.self) { index in
                                    Button(action: {
                                        playerManager.playChronicle(at: index)
                                    }) {
                                        HStack(spacing: 12) {
                                            Text(playerManager.programs[index].formattedTime)
                                                .font(.system(size: 14, weight: .bold))
                                                .foregroundColor(.white.opacity(0.6))
                                                .frame(width: 50, alignment: .leading)
                                            
                                            Text(playerManager.programs[index].title)
                                                .foregroundColor(.white)
                                                .font(.system(size: 16, weight: playerManager.currentChronicleIndex == index ? .bold : .regular))
                                            
                                            Spacer()
                                            
                                            if playerManager.currentChronicleIndex == index {
                                                Image(systemName: "waveform")
                                                    .foregroundColor(.white)
                                            }
                                        }
                                        .padding(.vertical, 12)
                                        .padding(.horizontal, 24)
                                        .background(playerManager.currentChronicleIndex == index ? Color.white.opacity(0.1) : Color.clear)
                                        .cornerRadius(10)
                                    }
                                }
                            }
                        }
                        .padding(.bottom, 20)
                    }
                }
                .refreshable {
                    try? await playerManager.setup()
                }
                
                Spacer(minLength: 10)
                
                // 3. Close Button (Safely positioned)
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundColor(.white)
                        .frame(width: 60, height: 60)
                        .background(Color.white.opacity(0.15))
                        .clipShape(Circle())
                        .overlay(Circle().stroke(Color.white.opacity(0.1), lineWidth: 1))
                }
                .accessibilityIdentifier("close_player_button")
                .padding(.bottom, 30) // Adjusted bottom padding
            }
        }
        .sheet(isPresented: $showRecordingSettings) {
            NavigationView {
                Form {
                    Section(header: Text("Début de l'enregistrement")) {
                        HStack {
                            Text("Heure")
                            Spacer()
                            Picker("Heure", selection: $selectedHour) {
                                ForEach(0..<24) { hour in
                                    Text("\(hour) h").tag(hour)
                                }
                            }
                            .pickerStyle(.menu)
                        }
                        
                        HStack {
                            Text("Minute")
                            Spacer()
                            Picker("Minute", selection: $selectedMinute) {
                                ForEach(0..<60) { minute in
                                    Text("\(minute) min").tag(minute)
                                }
                            }
                            .pickerStyle(.menu)
                        }
                    }
                    
                    Section {
                        Button(action: {
                            Task {
                                isSavingSettings = true
                                do {
                                    try await APIService.shared.setUserBaseTime(hour: selectedHour, minute: selectedMinute)
                                    // Update local global start time if needed
                                    Program.updateGlobalStartTime(hour: selectedHour, minute: selectedMinute)
                                    showRecordingSettings = false
                                } catch {
                                    print("❌ Error saving base time: \(error)")
                                }
                                isSavingSettings = false
                            }
                        }) {
                            HStack {
                                Spacer()
                                if isSavingSettings {
                                    ProgressView()
                                        .padding(.trailing, 10)
                                }
                                Text("Valider le réglage")
                                    .fontWeight(.bold)
                                Spacer()
                            }
                        }
                        .disabled(isSavingSettings)
                    }
                }
                .navigationTitle("Réglages Enregistrement")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Fermer") {
                            showRecordingSettings = false
                        }
                    }
                }
                .onAppear {
                    Task {
                        do {
                            let baseTime = try await APIService.shared.getUserBaseTime()
                            selectedHour = baseTime.hour
                            selectedMinute = baseTime.minute
                            // S'assurer que le modèle local est aussi à jour
                            Program.updateGlobalStartTime(hour: baseTime.hour, minute: baseTime.minute)
                        } catch {
                            print("⚠️ Impossible de récupérer l'heure de base: \(error)")
                        }
                    }
                }
            }
            .presentationDetents([.medium])
        }
    }
}

// Custom Slider for a cleaner look
struct CustomSlider: View {
    @Binding var value: Double
    var range: ClosedRange<Double>
    var onEditingChanged: (Bool) -> Void
    
    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Track
                Rectangle()
                    .fill(Color.white.opacity(0.3))
                    .frame(height: 4)
                
                // Active Track
                Rectangle()
                    .fill(Color.white)
                    .frame(width: CGFloat((value - range.lowerBound) / (range.upperBound - range.lowerBound)) * geometry.size.width, height: 4)
                
                // Thumb
                Circle()
                    .fill(Color.white)
                    .frame(width: 14, height: 14)
                    .offset(x: CGFloat((value - range.lowerBound) / (range.upperBound - range.lowerBound)) * geometry.size.width - 7)
                    .gesture(
                        DragGesture(minimumDistance: 0)
                            .onChanged { gesture in
                                onEditingChanged(true)
                                let newValue = Double(gesture.location.x / geometry.size.width) * (range.upperBound - range.lowerBound) + range.lowerBound
                                self.value = min(max(range.lowerBound, newValue), range.upperBound)
                            }
                            .onEnded { _ in
                                onEditingChanged(false)
                            }
                    )
            }
        }
        .frame(height: 14)
    }
}
