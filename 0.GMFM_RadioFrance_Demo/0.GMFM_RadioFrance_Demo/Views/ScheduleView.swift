//
//  ScheduleView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct ScheduleView: View {
    @Environment(\.presentationMode) var presentationMode
    @ObservedObject var playbackManager = PlaybackManager.shared
    @State private var isProgramming = false
    
    func saveProgramming() {
        isProgramming = true
        Task {
            do {
                // 1. Remove existing chronicles
                try await APIService.shared.removeChronicles()
                
                // 2. Add each chronicle in the new order
                let programsToSave = playbackManager.audioPlayerManager.programs
                for program in programsToSave {
                    try await APIService.shared.addChronicle(program: program)
                }
                
                // 4. Refresh the player's program list to match the new order
                try await playbackManager.audioPlayerManager.setup()
                
                DispatchQueue.main.async {
                    isProgramming = false
                    presentationMode.wrappedValue.dismiss()
                }
            } catch {
                print("❌ Erreur lors de la programmation: \(error)")
                DispatchQueue.main.async {
                    isProgramming = false
                }
            }
        }
    }
    
    var body: some View {
        ZStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 0) {
                // Header with Navigation and Date Selector
                VStack(spacing: 24) {
                    HStack {
                        Button(action: {
                            presentationMode.wrappedValue.dismiss()
                        }) {
                            Image(systemName: "chevron.left")
                                .font(.system(size: 20))
                                .foregroundColor(.white)
                        }
                        
                        Spacer()
                        
                        Text("Grille des programmes")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(.white)
                        
                        Spacer()
                        
                        Button(action: {
                            // Edit mode toggle could go here if using standard List edit mode
                        }) {
                            Text("Modifier")
                                .font(.system(size: 16))
                                .foregroundColor(.white)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 10)
                    
                    // Date Selector
                    HStack {
                        Text("Aujourd'hui")
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(.white)
                        
                        Spacer()
                        
                        HStack(spacing: 8) {
                            Button(action: {}) {
                                Image(systemName: "chevron.left")
                                    .padding(10)
                                    .background(Color.white.opacity(0.1))
                                    .clipShape(Circle())
                            }
                            
                            Button(action: {}) {
                                Image(systemName: "calendar")
                                    .padding(10)
                                    .background(Color.white.opacity(0.1))
                                    .clipShape(Circle())
                            }
                            
                            Button(action: {}) {
                                Image(systemName: "chevron.right")
                                    .padding(10)
                                    .background(Color.white.opacity(0.1))
                                    .clipShape(Circle())
                            }
                        }
                        .foregroundColor(.white)
                    }
                    .padding(.horizontal)
                }
                .padding(.bottom, 20)
                
                // Timeline List
                List {
                    ForEach(playbackManager.audioPlayerManager.programs) { program in
                        TimelineRow(program: program, isCurrent: playbackManager.audioPlayerManager.currentChronicleName == program.title)
                            .listRowBackground(Color.clear)
                            .listRowInsets(EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16))
                            .listRowSeparator(.hidden)
                    }
                    .onMove { from, to in
                        // Update local copy for dragging if needed, or update manager directly
                        var updatedPrograms = playbackManager.audioPlayerManager.programs
                        updatedPrograms.move(fromOffsets: from, toOffset: to)
                        playbackManager.audioPlayerManager.programs = updatedPrograms
                    }
                }
                .listStyle(.plain)
                .environment(\.editMode, .constant(.active)) // Always allow reordering
                
                Spacer()
                    .frame(height: 100)
            }
            
            // Programmer Button
            VStack {
                Button(action: {
                    saveProgramming()
                }) {
                    HStack {
                        if isProgramming {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .black))
                                .padding(.trailing, 8)
                        }
                        Text(isProgramming ? "Programmation..." : "Programmer")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(.black)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.white)
                    .clipShape(Capsule())
                    .padding(.horizontal, 24)
                    .padding(.bottom, 20)
                }
                .disabled(isProgramming)
            }
            .background(
                LinearGradient(gradient: Gradient(colors: [.clear, .black.opacity(0.8), .black]), startPoint: .top, endPoint: .bottom)
            )
        }
        .background(Color.black.ignoresSafeArea())
        .navigationBarHidden(true)
    }
}

struct TimelineRow: View {
    let program: Program
    let isCurrent: Bool
    
    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            // Time and Vertical Line
            VStack {
                Text(program.formattedTime)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(isCurrent ? .white : .white.opacity(0.6))
                
                // Vertical Line
                Rectangle()
                    .fill(Color.white.opacity(0.2))
                    .frame(width: 1)
                    .frame(maxHeight: .infinity)
            }
            .frame(width: 60)
            
            // Program Card
            HStack(spacing: 16) {
                // Thumbnail
                RoundedRectangle(cornerRadius: 12)
                    .fill(isCurrent ? Color.white.opacity(0.2) : program.color.opacity(0.3))
                    .frame(width: 80, height: 80)
                    .overlay(
                        Image(systemName: isCurrent ? "waveform" : "mic.fill")
                            .foregroundColor(.white)
                    )
                
                // Info
                VStack(alignment: .leading, spacing: 4) {
                    Text(program.title)
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(.white)
                        .lineLimit(2)
                    
                    if isCurrent {
                        Text("En cours de lecture")
                            .font(.system(size: 12))
                            .foregroundColor(.white.opacity(0.7))
                    }
                }
                
                Spacer()
            }
            .padding(12)
            .background(isCurrent ? Color(red: 0.88, green: 0, blue: 0.1).opacity(0.3) : Color.white.opacity(0.05))
            .clipShape(RoundedRectangle(cornerRadius: 24))
            .overlay(
                RoundedRectangle(cornerRadius: 24)
                    .stroke(isCurrent ? Color(red: 0.88, green: 0, blue: 0.1) : Color.clear, lineWidth: 1)
            )
            .padding(.bottom, 16)
        }
    }
}

#Preview {
    ScheduleView()
}
