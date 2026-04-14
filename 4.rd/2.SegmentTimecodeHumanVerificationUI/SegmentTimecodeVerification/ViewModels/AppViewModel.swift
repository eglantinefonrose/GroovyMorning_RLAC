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
    private var currentTimecodeURL: URL?
    
    @Published var selectedSegmentIndex: Int? {
        didSet {
            // Logic moved to markAsViewed to avoid view update cycles
        }
    }
    
    func markAsViewed(index: Int) {
        if !segments[index].isViewed {
            segments[index].isViewed = true
            if config.autoPlay {
                playCurrentSegment()
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
        
        // Reset current data
        segments = []
        srtBlocks = []
        selectedSegmentIndex = nil
        
        // Load Audio
        audioPlayer.load(url: mediaURL)
        
        // Load SRT
        if let transcriptionPath = config.transcriptionDirectoryPath {
            let exactURL = URL(fileURLWithPath: transcriptionPath).appendingPathComponent("\(baseName)_transcription.srt")

            if FileManager.default.fileExists(atPath: exactURL.path) {
                print("DEBUG: Loading SRT from: \(exactURL.path)")
                if let content = try? String(contentsOf: exactURL, encoding: .utf8) {
                    srtBlocks = SRTParser.parse(content: content)
                    print("DEBUG: Parsed \(srtBlocks.count) SRT blocks")
                }
            } else {
                print("DEBUG: SRT file not found. Expected: \(exactURL.path)")
                srtBlocks = []
            }
        }

        // Load Timecodes
        if let timecodePath = config.timecodeDirectoryPath {
            let exactURL = URL(fileURLWithPath: timecodePath).appendingPathComponent("\(baseName)_transcription_chronique.txt")

            if FileManager.default.fileExists(atPath: exactURL.path) {
                print("DEBUG: Loading Timecodes from: \(exactURL.path)")
                currentTimecodeURL = exactURL
                segments = FileService.shared.loadSegments(from: exactURL)
            } else {
                print("DEBUG: Timecode file not found. Expected: \(exactURL.path)")
                currentTimecodeURL = nil
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
    
    func updateSegmentBoundary(at index: Int, newTime: TimeInterval, isStart: Bool) {
        var segment = segments[index]
        let absoluteTime = newTime + config.timeOffset
        
        if isStart {
            segment.startTime = absoluteTime
        } else {
            segment.endTime = absoluteTime
        }
        
        segment.isModified = true
        segments[index] = segment
        saveSegments()
    }
    
    func loadManualSRT(url: URL) {
        if let content = try? String(contentsOf: url, encoding: .utf8) {
            srtBlocks = SRTParser.parse(content: content)
            print("DEBUG: Manually loaded \(srtBlocks.count) SRT blocks from \(url.lastPathComponent)")
        }
    }
    
    func loadManualTXT(url: URL) {
        print("DEBUG: Manually loading segments from \(url.path)")
        currentTimecodeURL = url
        segments = FileService.shared.loadSegments(from: url)
    }
    
    func syncOffset() {
        if let first = segments.first {
            config.timeOffset = first.startTime
            saveConfig()
            print("DEBUG: Offset synced to \(config.timeOffset)s")
        }
    }
    
    func saveSegments() {
        guard let url = currentTimecodeURL else { 
            print("ERROR: No timecode URL found to save segments")
            return 
        }
        
        do {
            try FileService.shared.saveSegments(segments, to: url)
            print("DEBUG: Segments saved successfully to \(url.lastPathComponent)")
        } catch {
            print("Error saving segments: \(error)")
        }
    }
}
