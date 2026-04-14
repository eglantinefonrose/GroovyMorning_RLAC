import Foundation
import SwiftUI
import Combine

@MainActor
class AppViewModel: ObservableObject {
    @Published var config = AppConfig()
    @Published var availableMediaFiles: [URL] = []
    @Published var selectedMediaURL: URL? {
        didSet {
            if let url = selectedMediaURL {
                loadData(for: url)
            }
        }
    }
    
    @Published var segments: [Segment] = []
    @Published var srtBlocks: [SRTBlock] = []
    @Published var selectedSegmentIndex: Int? {
        didSet {
            if let index = selectedSegmentIndex {
                Task { @MainActor in
                    segments[index].isViewed = true
                    if config.autoPlay {
                        playCurrentSegment()
                    }
                }
            }
        }
    }
    
    @Published var isEditingMode = false
    
    let audioPlayer = AudioPlayerService()
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        loadConfig()
        refreshMediaFiles()
    }
    
    func loadConfig() {
        if let data = UserDefaults.standard.data(forKey: "AppConfig"),
           let decoded = try? JSONDecoder().decode(AppConfig.self, from: data) {
            self.config = decoded
        }
    }
    
    func saveConfig() {
        if let encoded = try? JSONEncoder().encode(config) {
            UserDefaults.standard.set(encoded, forKey: "AppConfig")
        }
    }
    
    func refreshMediaFiles() {
        guard let path = config.mediaDirectoryPath else { return }
        let url = URL(fileURLWithPath: path)
        
        do {
            let files = try FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil)
            availableMediaFiles = files.filter { $0.pathExtension == "mp3" }.sorted(by: { $0.lastPathComponent < $1.lastPathComponent })
        } catch {
            print("Error refreshing media files: \(error)")
        }
    }
    
    private func loadData(for mediaURL: URL) {
        let baseName = mediaURL.deletingPathExtension().lastPathComponent
        print("DEBUG: Loading data for base name: \(baseName)")
        
        // Load Audio
        audioPlayer.load(url: mediaURL)
        
        // Load SRT
        if let transcriptionPath = config.transcriptionDirectoryPath {
            let srtURL = URL(fileURLWithPath: transcriptionPath).appendingPathComponent("\(baseName)_transcription.srt")
            print("DEBUG: Looking for SRT at: \(srtURL.path)")
            if FileManager.default.fileExists(atPath: srtURL.path) {
                if let content = try? String(contentsOf: srtURL, encoding: .utf8) {
                    srtBlocks = SRTParser.parse(content: content)
                    print("DEBUG: Parsed \(srtBlocks.count) SRT blocks")
                }
            } else {
                print("DEBUG: SRT file not found")
            }
        }
        
        // Load Timecodes
        if let timecodePath = config.timecodeDirectoryPath {
            let timecodeDirURL = URL(fileURLWithPath: timecodePath)
            let exactURL = timecodeDirURL.appendingPathComponent("\(baseName)_timecode_chronique.txt")
            
            var targetURL: URL? = nil
            
            if FileManager.default.fileExists(atPath: exactURL.path) {
                targetURL = exactURL
            } else {
                print("DEBUG: Exact timecode file not found, searching for alternatives...")
                // Search for any .txt file starting with baseName
                if let files = try? FileManager.default.contentsOfDirectory(at: timecodeDirURL, includingPropertiesForKeys: nil) {
                    targetURL = files.first { $0.lastPathComponent.hasPrefix(baseName) && $0.pathExtension == "txt" }
                }
            }
            
            if let foundURL = targetURL {
                print("DEBUG: Loading Timecodes from: \(foundURL.path)")
                segments = FileService.shared.loadSegments(from: foundURL)
            } else {
                print("DEBUG: No suitable Timecode file found in \(timecodePath)")
                segments = []
            }
        }
    }
    
    func playCurrentSegment() {
        guard let index = selectedSegmentIndex else { return }
        audioPlayer.playPreview(segment: segments[index], x: config.defaultXSeconds, y: config.defaultYSeconds)
    }
    
    func toggleEditMode() {
        isEditingMode.toggle()
    }
    
    func selectNextSegment() {
        guard let current = selectedSegmentIndex else {
            if !segments.isEmpty { selectedSegmentIndex = 0 }
            return
        }
        if current < segments.count - 1 {
            selectedSegmentIndex = current + 1
        }
    }
    
    func selectPreviousSegment() {
        guard let current = selectedSegmentIndex else { return }
        if current > 0 {
            selectedSegmentIndex = current - 1
        }
    }
    
    func updateSegmentTime(at index: Int, clickedTime: TimeInterval) {
        var segment = segments[index]
        // The clickedTime is relative to SRT (0-based), 
        // we need to add offset to get absolute time for TXT
        let absoluteTime = clickedTime + config.timeOffset
        
        let midPoint = (segment.startTime + segment.endTime) / 2
        
        if absoluteTime < midPoint {
            segment.startTime = absoluteTime
        } else {
            segment.endTime = absoluteTime
        }
        
        segment.isModified = true
        segments[index] = segment
        saveSegments()
    }
    
    func syncOffset() {
        if let first = segments.first {
            config.timeOffset = first.startTime
            saveConfig()
            print("DEBUG: Offset synced to \(config.timeOffset)s")
        }
    }
    
    func saveSegments() {
        guard let mediaURL = selectedMediaURL, let timecodePath = config.timecodeDirectoryPath else { return }
        let baseName = mediaURL.deletingPathExtension().lastPathComponent
        let txtURL = URL(fileURLWithPath: timecodePath).appendingPathComponent("\(baseName)_timecode_chronique.txt")
        
        do {
            try FileService.shared.saveSegments(segments, to: txtURL)
        } catch {
            print("Error saving segments: \(error)")
        }
    }
}
