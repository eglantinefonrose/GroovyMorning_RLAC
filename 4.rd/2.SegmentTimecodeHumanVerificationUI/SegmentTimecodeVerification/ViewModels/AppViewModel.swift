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
                triggerLoad(for: url)
            } else {
                clearData()
            }
        }
    }
    
    @Published var segments: [Segment] = []
    @Published var srtBlocks: [SRTBlock] = []
    @Published var errorMessage: String?
    @Published var isLoading: Bool = false
    @Published var isShowingAddSegment: Bool = false
    
    private var currentTimecodeURL: URL?
    private var loadTask: Task<Void, Never>?
    
    @Published var selectedSegmentId: UUID?
    
    var selectedSegmentIndex: Int? {
        segments.firstIndex(where: { $0.id == selectedSegmentId })
    }
    
    @Published var isEditingMode = false
    
    let audioPlayer = AudioPlayerService()
    
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
        guard let path = config.mediaDirectoryPath, !path.isEmpty else { return }
        let expandedPath = (path as NSString).expandingTildeInPath
        let url = URL(fileURLWithPath: expandedPath)
        
        do {
            let files = try FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil)
            let mp3s = files.filter { $0.pathExtension.lowercased() == "mp3" }
                .sorted(by: { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending })
            
            self.availableMediaFiles = mp3s
            print("DEBUG: Refreshed media files, found \(mp3s.count) MP3s in \(expandedPath)")
        } catch {
            print("ERROR: Could not refresh media files at \(expandedPath): \(error)")
            self.errorMessage = "Impossible de lire le dossier média : \(error.localizedDescription)"
        }
    }
    
    private func triggerLoad(for url: URL) {
        loadTask?.cancel()
        loadTask = Task {
            await loadData(for: url)
        }
    }
    
    private func clearData() {
        audioPlayer.stop()
        segments = []
        srtBlocks = []
        selectedSegmentId = nil
        errorMessage = nil
        currentTimecodeURL = nil
    }
    
    private func loadData(for mediaURL: URL) async {
        let baseName = mediaURL.deletingPathExtension().lastPathComponent
        print("DEBUG: === Starting loadData for \(baseName) ===")
        
        await MainActor.run {
            self.isLoading = true
            self.clearData()
        }
        
        // Ensure audio is loaded on MainActor
        await MainActor.run {
            audioPlayer.load(url: mediaURL)
        }
        
        if Task.isCancelled { return }

        // Load SRT
        if let srtURL = findRelatedFile(for: baseName, in: config.transcriptionDirectoryPath, extensions: ["srt"]) {
            do {
                let content = try String(contentsOf: srtURL, encoding: .utf8)
                let blocks = SRTParser.parse(content: content)
                await MainActor.run {
                    self.srtBlocks = blocks
                    print("DEBUG: Loaded \(blocks.count) SRT blocks from \(srtURL.lastPathComponent)")
                    if blocks.isEmpty {
                        self.errorMessage = "Le fichier SRT est vide ou mal formaté (\(srtURL.lastPathComponent))."
                    }
                }
            } catch {
                await MainActor.run {
                    self.errorMessage = "Erreur lecture SRT : \(error.localizedDescription)"
                }
            }
        } else {
            print("DEBUG: No SRT found for \(baseName)")
        }

        if Task.isCancelled { return }

        // Load Timecodes
        if let txtURL = findRelatedFile(for: baseName, in: config.timecodeDirectoryPath, extensions: ["txt"]) {
            let loadedSegments = FileService.shared.loadSegments(from: txtURL)
            await MainActor.run {
                self.segments = loadedSegments
                self.currentTimecodeURL = txtURL
                print("DEBUG: Loaded \(loadedSegments.count) segments from \(txtURL.lastPathComponent)")
            }
        } else {
            print("DEBUG: No TXT found, preparing default path")
            if let timecodePath = config.timecodeDirectoryPath, !timecodePath.isEmpty {
                let expandedPath = (timecodePath as NSString).expandingTildeInPath
                let dirURL = URL(fileURLWithPath: expandedPath)
                await MainActor.run {
                    self.currentTimecodeURL = dirURL.appendingPathComponent("\(baseName)_transcription_chronique.txt")
                }
            }
        }
        
        await MainActor.run {
            self.isLoading = false
        }
    }
    
    private func findRelatedFile(for baseName: String, in directoryPath: String?, extensions: [String]) -> URL? {
        guard let path = directoryPath, !path.isEmpty else { return nil }
        let expandedPath = (path as NSString).expandingTildeInPath
        let dirURL = URL(fileURLWithPath: expandedPath)
        
        do {
            let files = try FileManager.default.contentsOfDirectory(at: dirURL, includingPropertiesForKeys: nil)
            return files.first { fileURL in
                let fileName = fileURL.lastPathComponent.lowercased()
                let baseLower = baseName.lowercased()
                // Be flexible: starts with baseName AND has correct extension
                return fileName.hasPrefix(baseLower) && extensions.contains(fileURL.pathExtension.lowercased())
            }
        } catch {
            print("DEBUG: Error searching in \(expandedPath): \(error)")
            return nil
        }
    }

    func refreshCurrentMedia() {
        if let url = selectedMediaURL {
            triggerLoad(for: url)
        }
    }
    
    func markAsViewed(id: UUID) {
        if let index = segments.firstIndex(where: { $0.id == id }) {
            if !segments[index].isViewed {
                segments[index].isViewed = true
                if config.autoPlay {
                    playCurrentSegment()
                }
            }
        }
    }
    
    func playCurrentSegment() {
        guard let id = selectedSegmentId,
              let segment = segments.first(where: { $0.id == id }) else { return }
        audioPlayer.playPreview(segment: segment, x: config.defaultXSeconds, y: config.defaultYSeconds)
    }
    
    func toggleEditMode() {
        isEditingMode.toggle()
    }
    
    func selectNextSegment() {
        guard let currentId = selectedSegmentId,
              let currentIndex = segments.firstIndex(where: { $0.id == currentId }) else {
            if !segments.isEmpty { selectedSegmentId = segments[0].id }
            return
        }
        if currentIndex < segments.count - 1 {
            selectedSegmentId = segments[currentIndex + 1].id
        }
    }
    
    func selectPreviousSegment() {
        guard let currentId = selectedSegmentId,
              let currentIndex = segments.firstIndex(where: { $0.id == currentId }) else { return }
        if currentIndex > 0 {
            selectedSegmentId = segments[currentIndex - 1].id
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
            errorMessage = srtBlocks.isEmpty ? "Fichier SRT mal formaté ou vide." : nil
        }
    }
    
    func loadManualTXT(url: URL) {
        currentTimecodeURL = url
        segments = FileService.shared.loadSegments(from: url)
        selectedSegmentId = nil
    }
    
    func syncOffset() {
        if let first = segments.first {
            config.timeOffset = first.startTime
            saveConfig()
        }
    }

    func createNewSegment() {
        let insertIndex: Int
        let startTime: TimeInterval
        
        if let currentId = selectedSegmentId,
           let currentIndex = segments.firstIndex(where: { $0.id == currentId }) {
            insertIndex = currentIndex + 1
            startTime = segments[currentIndex].endTime
        } else {
            insertIndex = segments.count
            startTime = segments.last?.endTime ?? 0
        }
        
        let newSegment = Segment(startTime: startTime, endTime: startTime + 10, title: "Nouvelle chronique", isModified: true, isNew: true)
        
        if insertIndex < segments.count {
            segments.insert(newSegment, at: insertIndex)
        } else {
            segments.append(newSegment)
        }
        
        selectedSegmentId = newSegment.id
        isEditingMode = true
        saveSegments()
    }

    func renameSegment(id: UUID, newTitle: String) {
        if let index = segments.firstIndex(where: { $0.id == id }) {
            segments[index].title = newTitle
            segments[index].isModified = true
            saveSegments()
        }
    }

    func addSegment(title: String, startTime: TimeInterval, endTime: TimeInterval) {
        let newSegment = Segment(startTime: startTime, endTime: endTime, title: title, isModified: true, isNew: false)
        segments.append(newSegment)
        segments.sort { $0.startTime < $1.startTime }
        saveSegments()
    }

    func deleteSegment(at index: Int) {
        guard index >= 0 && index < segments.count else { return }
        let segmentId = segments[index].id
        segments.remove(at: index)
        if selectedSegmentId == segmentId {
            selectedSegmentId = nil
        }
        saveSegments()
    }
    
    func saveSegments() {
        guard let url = currentTimecodeURL else { return }
        do {
            try FileService.shared.saveSegments(segments, to: url)
        } catch {
            print("Error saving segments: \(error)")
            errorMessage = "Erreur sauvegarde : \(error.localizedDescription)"
        }
    }
}
