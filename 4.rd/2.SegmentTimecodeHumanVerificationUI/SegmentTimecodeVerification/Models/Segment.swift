import Foundation

struct Segment: Identifiable, Equatable {
    let id = UUID()
    var startTime: TimeInterval
    var endTime: TimeInterval
    let title: String
    var isModified: Bool = false
    var isViewed: Bool = false
    
    var duration: TimeInterval {
        endTime - startTime
    }
}
