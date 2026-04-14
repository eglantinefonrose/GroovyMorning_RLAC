import SwiftUI

struct TranscriptionView: View {
    @ObservedObject var viewModel: AppViewModel
    
    var body: some View {
        VStack {
            if let index = viewModel.selectedSegmentIndex {
                let segment = viewModel.segments[index]
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        if viewModel.isEditingMode {
                            // Edition mode: show context
                            let contextBlocks = getContextBlocks(for: segment)
                            ForEach(contextBlocks) { block in
                                Text(block.text)
                                    .padding(8)
                                    .background(getBlockColor(block, for: segment))
                                    .cornerRadius(4)
                                    .onTapGesture {
                                        viewModel.updateSegmentTime(at: index, clickedTime: block.startTime)
                                    }
                            }
                        } else if viewModel.config.validationMode == .text {
                            // Text Validation mode: show Start X and End Y snippets
                            VStack(alignment: .leading, spacing: 20) {
                                VStack(alignment: .leading, spacing: 5) {
                                    Label("Start Context (\(viewModel.config.defaultXSeconds)s)", systemImage: "arrow.right.to.line")
                                        .font(.caption)
                                        .foregroundColor(.blue)
                                    Text(getSnippet(start: segment.startTime - viewModel.config.timeOffset, end: segment.startTime + Double(viewModel.config.defaultXSeconds) - viewModel.config.timeOffset))
                                        .font(.system(.body, design: .monospaced))
                                        .padding()
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(Color.blue.opacity(0.1))
                                        .cornerRadius(8)
                                }
                                
                                VStack(alignment: .leading, spacing: 5) {
                                    Label("End Context (\(viewModel.config.defaultYSeconds)s)", systemImage: "arrow.left.to.line")
                                        .font(.caption)
                                        .foregroundColor(.orange)
                                    Text(getSnippet(start: max(segment.startTime - viewModel.config.timeOffset, segment.endTime - Double(viewModel.config.defaultYSeconds) - viewModel.config.timeOffset), end: segment.endTime - viewModel.config.timeOffset))
                                        .font(.system(.body, design: .monospaced))
                                        .padding()
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(Color.orange.opacity(0.1))
                                        .cornerRadius(8)
                                }
                            }
                        } else {
                            // Visualisation mode: only segment text
                            let segmentBlocks = viewModel.srtBlocks.filter { 
                                $0.startTime >= segment.startTime && $0.endTime <= segment.endTime 
                            }
                            Text(segmentBlocks.map { $0.text }.joined(separator: " "))
                                .font(.body)
                                .lineSpacing(5)
                        }
                    }
                    .padding()
                }
            } else {
                Text("Select a sequence to see transcription")
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.textBackgroundColor))
    }
    
    private func getSnippet(start: TimeInterval, end: TimeInterval) -> String {
        let blocks = viewModel.srtBlocks.filter {
            $0.endTime > start && $0.startTime < end
        }
        if blocks.isEmpty { return "No transcription found for this range." }
        return blocks.map { "[\(formatTime($0.startTime))] \($0.text)" }.joined(separator: "\n")
    }
    
    private func formatTime(_ time: TimeInterval) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        let ms = Int((time.truncatingRemainder(dividingBy: 1)) * 1000)
        return String(format: "%02d:%02d,%03d", minutes, seconds, ms)
    }
    
    private func getContextBlocks(for segment: Segment) -> [SRTBlock] {
        // Find blocks around the segment, taking offset into account.
        let adjustedStart = segment.startTime - viewModel.config.timeOffset
        let adjustedEnd = segment.endTime - viewModel.config.timeOffset
        
        return viewModel.srtBlocks.filter {
            $0.endTime >= adjustedStart - 30 && $0.startTime <= adjustedEnd + 30
        }
    }
    
    private func getBlockColor(_ block: SRTBlock, for segment: Segment) -> Color {
        let adjustedStart = segment.startTime - viewModel.config.timeOffset
        let adjustedEnd = segment.endTime - viewModel.config.timeOffset
        
        if block.startTime >= adjustedStart && block.endTime <= adjustedEnd {
            return Color.blue.opacity(0.2)
        } else {
            return Color.gray.opacity(0.1)
        }
    }
}
