//
//  RadioStation.swift
//  0.GMFM_RadioFrance_Demo
//
//  Created by Eglantine Fonrose on 05/04/2026.
//


import Foundation
import SwiftUI

struct RadioStation: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let color: Color
    let logoName: String
    let currentShow: String
    let subtitle: String
    let hostImage: String
}

struct Program: Identifiable, Equatable {
    let id = UUID()
    let time: String
    let title: String
    let thumbnail: String
    let color: Color
    let startTime: Int
    let duration: Int
    
    // Heure de début globale (initialement 7h00)
    static var globalStartTime = (hour: 7, minute: 0)
    
    static func updateGlobalStartTime(hour: Int, minute: Int) {
        globalStartTime = (hour: hour, minute: minute)
    }
    
    // Calcule l'heure d'affichage basée sur startTime (secondes) et globalStartTime
    var formattedTime: String {
        // Conversion de l'heure de début globale en secondes totales
        let baseSeconds = (Program.globalStartTime.hour * 3600) + (Program.globalStartTime.minute * 60)
        
        // Ajout du startTime de la chronique (startTime est en secondes depuis le début du dossier)
        let totalSeconds = baseSeconds + startTime
        
        let hours = (totalSeconds / 3600) % 24
        let minutes = (totalSeconds % 3600) / 60
        
        return String(format: "%02dh%02d", hours, minutes)
    }
    
    static func == (lhs: Program, rhs: Program) -> Bool {
        lhs.id == rhs.id
    }
}

struct FeaturedContent: Identifiable {
    let id = UUID()
    let title: String
    let subtext: String
    let duration: String
    let color: Color
}
