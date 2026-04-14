import Foundation

@MainActor
class FileService {
    static let shared = FileService()
    
    func loadSegments(from url: URL) -> [Segment] {
        print("DEBUG: Loading segments from \(url.path)")
        guard let content = try? String(contentsOf: url, encoding: .utf8) else { 
            print("ERROR: Could not read file at \(url.path)")
            return [] 
        }
        
        let lines = content.components(separatedBy: .newlines)
        print("DEBUG: Found \(lines.count) lines in file")
        var segments: [Segment] = []
        
        // Regex robuste : gère [HH:mm:ss] ou HH:mm:ss, avec ou sans crochets, avec ou sans millisecondes
        let timestampPattern = #"\[?(\d{1,2}:\d{2}:\d{2}(?:[.,]\d{3})?)\]?"#
        let pattern = #"^\s*"# + timestampPattern + #"\s*-\s*"# + timestampPattern + #"\s*[:\s\-]*(.*)$"#
        print("DEBUG: Using regex pattern: \(pattern)")
        
        let regex = try? NSRegularExpression(pattern: pattern, options: [])
        
        for (index, line) in lines.enumerated() {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            
            if let match = regex?.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)) {
                // Group 1: Start, Group 2: End, Group 3: Title
                if let startRange = Range(match.range(at: 1), in: trimmed),
                   let endRange = Range(match.range(at: 2), in: trimmed),
                   let titleRange = Range(match.range(at: 3), in: trimmed) {
                    
                    let startStr = String(trimmed[startRange])
                    let endStr = String(trimmed[endRange])
                    let title = String(trimmed[titleRange]).trimmingCharacters(in: .whitespacesAndNewlines)
                    
                    if let start = parseTimestamp(startStr), let end = parseTimestamp(endStr) {
                        segments.append(Segment(startTime: start, endTime: end, title: title.isEmpty ? "Untitled" : title))
                    } else {
                        print("DEBUG: Line \(index + 1) - Failed to parse timestamps: \(startStr) or \(endStr)")
                    }
                }
            } else {
                print("DEBUG: Line \(index + 1) - No match for: '\(trimmed)'")
            }
        }
        print("DEBUG: Successfully parsed \(segments.count) segments")
        return segments
    }
    
    func saveSegments(_ segments: [Segment], to url: URL) throws {
        let directory = url.deletingLastPathComponent()
        let backupDir = directory.appendingPathComponent(".original_before_manual_correction")
        
        if !FileManager.default.fileExists(atPath: backupDir.path) {
            try FileManager.default.createDirectory(at: backupDir, withIntermediateDirectories: true)
        }
        
        let backupFile = backupDir.appendingPathComponent(url.lastPathComponent)
        if !FileManager.default.fileExists(atPath: backupFile.path) {
            try FileManager.default.copyItem(at: url, to: backupFile)
        }
        
        let content = segments.map { segment in
            "\(formatTimestamp(segment.startTime)) - \(formatTimestamp(segment.endTime)) : \(segment.title)"
        }.joined(separator: "\n")
        
        try content.write(to: url, atomically: true, encoding: .utf8)
    }
    
    private func parseTimestamp(_ str: String) -> TimeInterval? {
        let clean = str.replacingOccurrences(of: "[", with: "").replacingOccurrences(of: "]", with: "").replacingOccurrences(of: ",", with: ".")
        let parts = clean.components(separatedBy: ":")
        if parts.count == 3 {
            let hours = Double(parts[0]) ?? 0
            let minutes = Double(parts[1]) ?? 0
            let seconds = Double(parts[2]) ?? 0
            return hours * 3600 + minutes * 60 + seconds
        } else if parts.count == 2 {
            let minutes = Double(parts[0]) ?? 0
            let seconds = Double(parts[1]) ?? 0
            return minutes * 60 + seconds
        }
        return nil
    }
    
    private func formatTimestamp(_ time: TimeInterval) -> String {
        let hours = Int(time) / 3600
        let minutes = (Int(time) % 3600) / 60
        let seconds = Int(time) % 60
        let milliseconds = Int((time.truncatingRemainder(dividingBy: 1)) * 1000)
        return String(format: "%02d:%02d:%02d.%03d", hours, minutes, seconds, milliseconds)
    }
}
