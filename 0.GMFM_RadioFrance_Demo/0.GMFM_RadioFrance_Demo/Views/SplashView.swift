//
//  SplashView.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct SplashView: View {
    @State private var isActive = false
    @State private var opacity = 1.0
    
    var body: some View {
        if isActive {
            MainTabView()
        } else {
            ZStack {
                // Using the exact screenshot image from assets
                Image("SplashImage")
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .ignoresSafeArea()
            }
            .opacity(opacity)
            .onAppear {
                // Short delay to show the splash before transition
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                    withAnimation(.easeInOut(duration: 0.5)) {
                        self.opacity = 0.0
                    }
                    
                    // Final switch to main view after fade
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        self.isActive = true
                    }
                }
            }
        }
    }
}

#Preview {
    SplashView()
}
