import Foundation

class SRTParser {
    static func parse(content: String) -> [SRTBlock] {
        let lines = content.components(separatedBy: .newlines)
        var blocks: [SRTBlock] = []
        
        // Regex to match timestamps like 00:00:00.000 or 00:00:00,000
        let timePattern = #"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"#
        let rangePattern = "\(timePattern)\\s*-->\\s*\(timePattern)"
        
        var idCounter = 1
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            
            // Try to match the time range in the line
            if let range = trimmed.range(of: #".*?(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3}).*?"#, options: .regularExpression) {
                
                let timePart = String(trimmed[range])
                // Extract timestamps
                let times = extractTimes(from: timePart)
                
                if times.count == 2 {
                    // Extract text: everything after the timestamp block or inside the line
                    // For format: [start --> end] Text
                    var text = trimmed
                    text.removeSubrange(range)
                    text = text.trimmingCharacters(in: CharacterSet(charactersIn: "[] ").union(.whitespacesAndNewlines))
                    
                    blocks.append(SRTBlock(id: idCounter, startTime: times[0], endTime: times[1], text: text))
                    idCounter += 1
                }
            }
        }
        
        // If no blocks were found with the line-based method, it might be a standard multi-line SRT
        if blocks.isEmpty {
            return parseStandardSRT(lines: lines)
        }
        
        return blocks
    }
    
    private static func extractTimes(from text: String) -> [TimeInterval] {
        let pattern = #"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"#
        let regex = try? NSRegularExpression(pattern: pattern)
        let matches = regex?.matches(in: text, range: NSRange(text.startIndex..., in: text)) ?? []
        
        return matches.compactMap { match in
            if let range = Range(match.range, in: text) {
                return parseTime(String(text[range]))
            }
            return nil
        }
    }
    
    private static func parseStandardSRT(lines: [String]) -> [SRTBlock] {
        var blocks: [SRTBlock] = []
        var currentId: Int?
        var currentTimeRange: (TimeInterval, TimeInterval)?
        var currentTextLines: [String] = []
        
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                if let id = currentId, let range = currentTimeRange {
                    blocks.append(SRTBlock(id: id, startTime: range.0, endTime: range.1, text: currentTextLines.joined(separator: " ")))
                }
                currentId = nil
                currentTimeRange = nil
                currentTextLines = []
                continue
            }
            
            if currentId == nil, let id = Int(trimmed) {
                currentId = id
            } else if currentTimeRange == nil, let range = parseTimeRange(trimmed) {
                currentTimeRange = range
            } else {
                currentTextLines.append(trimmed)
            }
        }
        return blocks
    }
    
    private static func parseTimeRange(_ line: String) -> (TimeInterval, TimeInterval)? {
        let parts = line.components(separatedBy: " --> ")
        guard parts.count == 2,
              let start = parseTime(parts[0]),
              let end = parseTime(parts[1]) else { return nil }
        return (start, end)
    }
    
    private static func parseTime(_ timeStr: String) -> TimeInterval? {
        let cleanStr = timeStr.replacingOccurrences(of: "[", with: "").replacingOccurrences(of: "]", with: "").replacingOccurrences(of: ",", with: ".")
        let parts = cleanStr.components(separatedBy: ":")
        guard parts.count == 3 else { return nil }
        
        let hours = Double(parts[0]) ?? 0
        let minutes = Double(parts[1]) ?? 0
        let seconds = Double(parts[2]) ?? 0
        
        return hours * 3600 + minutes * 60 + seconds
    }
}
