import Foundation

enum ValidationMode: String, Codable, CaseIterable {
    case audio = "Audio"
    case text = "Text"
}

struct AppConfig: Codable {
    var mediaDirectoryPath: String?
    var transcriptionDirectoryPath: String?
    var timecodeDirectoryPath: String?
    var defaultXSeconds: Int = 5
    var defaultYSeconds: Int = 3
    var autoPlay: Bool = true
    var validationMode: ValidationMode = .audio
    var timeOffset: TimeInterval = 0
}
