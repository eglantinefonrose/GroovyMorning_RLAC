import Foundation

struct Segment: Identifiable, Equatable {
    let id = UUID()
    var startTime: TimeInterval
    var endTime: TimeInterval
    var title: String
    var isModified: Bool = false
    var isViewed: Bool = false
    var isNew: Bool = false
    
    var duration: TimeInterval {
        endTime - startTime
    }
}
