import SwiftUI
import UniformTypeIdentifiers

struct TranscriptionView: View {
    @ObservedObject var viewModel: AppViewModel
    
    var body: some View {
        VStack {
            if let index = viewModel.selectedSegmentIndex {
                let segment = viewModel.segments[index]
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        if viewModel.isEditingMode {
                            // Edition mode: Separate Start and End
                            VStack(alignment: .leading, spacing: 10) {
                                Label("Edit START boundary", systemImage: "arrow.right.to.line")
                                    .font(.headline).foregroundColor(.blue)
                                
                                let startContext = getContextBlocks(for: segment.startTime)
                                ForEach(startContext) { block in
                                    Text(block.text)
                                        .padding(8)
                                        .background(isSameTime(block.startTime, segment.startTime) ? Color.blue.opacity(0.3) : Color.gray.opacity(0.1))
                                        .cornerRadius(4)
                                        .onTapGesture {
                                            viewModel.updateSegmentBoundary(at: index, newTime: block.startTime, isStart: true)
                                        }
                                }
                            }
                            
                            Divider()
                            
                            VStack(alignment: .leading, spacing: 10) {
                                Label("Edit END boundary", systemImage: "arrow.left.to.line")
                                    .font(.headline).foregroundColor(.orange)
                                
                                let endContext = getContextBlocks(for: segment.endTime)
                                ForEach(endContext) { block in
                                    Text(block.text)
                                        .padding(8)
                                        .background(isSameTime(block.startTime, segment.endTime) ? Color.orange.opacity(0.3) : Color.gray.opacity(0.1))
                                        .cornerRadius(4)
                                        .onTapGesture {
                                            viewModel.updateSegmentBoundary(at: index, newTime: block.startTime, isStart: false)
                                        }
                                }
                            }
                        } else if viewModel.config.validationMode == .text {
                            // Text Validation mode
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
                            // Visualisation mode
                            let segmentBlocks = viewModel.srtBlocks.filter { 
                                $0.startTime >= (segment.startTime - viewModel.config.timeOffset) && 
                                $0.endTime <= (segment.endTime - viewModel.config.timeOffset) 
                            }
                            Text(segmentBlocks.map { $0.text }.joined(separator: " "))
                                .font(.body)
                                .lineSpacing(5)
                        }
                    }
                    .padding()
                }
                .onAppear {
                    viewModel.markAsViewed(index: index)
                }
                .id(index)
            } else if viewModel.srtBlocks.isEmpty {
                VStack(spacing: 20) {
                    ContentUnavailableView {
                        Label("No Transcription", systemImage: "captions.bubble")
                    } description: {
                        Text("The SRT file for this media could not be found automatically.")
                    } actions: {
                        Button("Select SRT Manually") {
                            selectFile(extensions: ["srt"]) { url in
                                viewModel.loadManualSRT(url: url)
                            }
                        }
                    }
                }
            } else {
                Text("Select a sequence to see transcription")
                    .foregroundColor(.secondary)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.textBackgroundColor))
    }
    
    private func isSameTime(_ t1: TimeInterval, _ t2: TimeInterval) -> Bool {
        abs(t1 - (t2 - viewModel.config.timeOffset)) < 0.001
    }
    
    private func selectFile(extensions: [String], completion: @escaping (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = extensions.compactMap { UTType(filenameExtension: $0) }
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                completion(url)
            }
        }
    }
    
    private func getSnippet(start: TimeInterval, end: TimeInterval) -> String {
        let blocks = viewModel.srtBlocks.filter {
            $0.endTime > start && $0.startTime < end
        }
        if blocks.isEmpty { 
            return "No transcription found for this range (\(formatTime(start)) - \(formatTime(end)))." 
        }
        return blocks.map { "[\(formatTime($0.startTime))] \($0.text)" }.joined(separator: "\n")
    }
    
    private func formatTime(_ time: TimeInterval) -> String {
        let absoluteTime = abs(time)
        let hours = Int(absoluteTime) / 3600
        let minutes = (Int(absoluteTime) % 3600) / 60
        let seconds = Int(absoluteTime) % 60
        let ms = Int((absoluteTime.truncatingRemainder(dividingBy: 1)) * 1000)
        
        let sign = time < 0 ? "-" : ""
        if hours > 0 {
            return String(format: "%@%02d:%02d:%02d,%03d", sign, hours, minutes, seconds, ms)
        } else {
            return String(format: "%@%02d:%02d,%03d", sign, minutes, seconds, ms)
        }
    }
    
    private func getContextBlocks(for absoluteTime: TimeInterval) -> [SRTBlock] {
        let adjustedTime = absoluteTime - viewModel.config.timeOffset
        return viewModel.srtBlocks.filter {
            $0.endTime >= adjustedTime - 30 && $0.startTime <= adjustedTime + 30
        }
    }
}
