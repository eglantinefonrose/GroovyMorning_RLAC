import Foundation

struct SRTBlock: Identifiable, Equatable {
    let id: Int
    let startTime: TimeInterval
    let endTime: TimeInterval
    let text: String
}
