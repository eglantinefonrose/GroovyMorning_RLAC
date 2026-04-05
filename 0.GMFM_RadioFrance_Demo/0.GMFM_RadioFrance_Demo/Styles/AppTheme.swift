//
//  AppTheme.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import SwiftUI

struct AppTheme {
    static let backgroundColor = Color.black
    static let cardBackgroundColor = Color(white: 0.1)
    static let secondaryTextColor = Color.gray
    static let accentColor = Color.white
    
    // Stations colors
    static let interRed = Color(red: 226/255, green: 0, blue: 26/255)
    static let infoYellow = Color(red: 255/255, green: 208/255, blue: 0)
    static let culturePurple = Color(red: 117/255, green: 51/255, blue: 142/255)
    static let musiquePink = Color(red: 229/255, green: 0, blue: 125/255)
    
    // Gradient for Splash Screen
    static let splashGradient = LinearGradient(
        colors: [
            Color(red: 0.94, green: 0.35, blue: 0.52), // Pinkish top
            Color(red: 0.73, green: 0.33, blue: 0.61), // Middle purple/pink
            Color(red: 0.45, green: 0.29, blue: 0.65)  // Bottom purple
        ],
        startPoint: .top,
        endPoint: .bottom
    )
}
