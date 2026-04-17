import SwiftUI
import UniformTypeIdentifiers

struct BlockView: View {
    let block: SRTBlock
    let isSelected: Bool
    let isMatch: Bool
    let selectionColor: Color
    let onTap: () -> Void
    
    var body: some View {
        Text(block.text)
            .padding(8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(isSelected ? selectionColor.opacity(0.3) : (isMatch ? Color.yellow.opacity(0.4) : Color.gray.opacity(0.1)))
            .border(isMatch ? Color.yellow : Color.clear, width: 2)
            .cornerRadius(4)
            .onTapGesture(perform: onTap)
    }
}

struct EditColumnView: View {
    let title: String
    let icon: String
    let color: Color
    let prefix: String
    let blocks: [SRTBlock]
    let selectedTime: TimeInterval
    let searchText: String
    let isSameTime: (TimeInterval, TimeInterval) -> Bool
    let onSelect: (TimeInterval) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(title, systemImage: icon)
                .font(.headline).foregroundColor(color)
                .padding(.horizontal)
                .padding(.top, 8)
            
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(blocks) { block in
                            BlockView(
                                block: block,
                                isSelected: isSameTime(block.startTime, selectedTime),
                                isMatch: !searchText.isEmpty && block.text.localizedCaseInsensitiveContains(searchText),
                                selectionColor: color,
                                onTap: { onSelect(block.startTime) }
                            )
                            .id("\(prefix)-\(block.id)")
                        }
                    }
                    .padding()
                }
                .onAppear {
                    scrollToSelected(proxy: proxy)
                }
                .onChange(of: blocks) { _, _ in
                    scrollToSelected(proxy: proxy)
                }
                .onChange(of: searchText) { _, newValue in

                    if !newValue.isEmpty, let firstMatch = blocks.first(where: { $0.text.localizedCaseInsensitiveContains(newValue) }) {
                        withAnimation {
                            proxy.scrollTo("\(prefix)-\(firstMatch.id)", anchor: .center)
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func scrollToSelected(proxy: ScrollViewProxy) {
        if let selectedBlock = blocks.first(where: { isSameTime($0.startTime, selectedTime) }) {
            DispatchQueue.main.async {
                withAnimation {
                    proxy.scrollTo("\(prefix)-\(selectedBlock.id)", anchor: .center)
                }
            }
        }
    }
}

struct TranscriptionView: View {
    @ObservedObject var viewModel: AppViewModel
    @State private var searchText: String = ""
    
    var body: some View {
        VStack(spacing: 0) {
            if let error = viewModel.errorMessage {
                Text(error)
                    .foregroundColor(.white)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color.red)
            }
            
            if viewModel.isEditingMode && viewModel.selectedSegmentId != nil {
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("Rechercher dans la transcription...", text: $searchText)
                        .textFieldStyle(.roundedBorder)
                    if !searchText.isEmpty {
                        Button {
                            searchText = ""
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding()
                .background(Color(NSColor.windowBackgroundColor))
            }

            if let segmentId = viewModel.selectedSegmentId,
               let currentIndex = viewModel.segments.firstIndex(where: { $0.id == segmentId }) {
                let segment = viewModel.segments[currentIndex]
                let previousSegment = currentIndex > 0 ? viewModel.segments[currentIndex - 1] : nil
                let nextSegment = currentIndex < viewModel.segments.count - 1 ? viewModel.segments[currentIndex + 1] : nil
                
                Group {
                    if viewModel.isEditingMode {
                        // Edition mode: Two independent columns sharing space
                        HStack(spacing: 0) {
                            EditColumnView(
                                title: "Edit END boundary",
                                icon: "arrow.left.to.line",
                                color: .orange,
                                prefix: "end",
                                blocks: getBlocksInRange(start: segment.endTime - 120, end: max(nextSegment?.startTime ?? segment.endTime, segment.endTime + 600) + 60),
                                selectedTime: segment.endTime,
                                searchText: searchText,
                                isSameTime: isSameTime,
                                onSelect: { viewModel.updateSegmentBoundary(at: currentIndex, newTime: $0, isStart: false) }
                            )
                            
                            Divider()
                            
                            EditColumnView(
                                title: "Edit START boundary",
                                icon: "arrow.right.to.line",
                                color: .blue,
                                prefix: "start",
                                blocks: getBlocksInRange(start: min(previousSegment?.endTime ?? segment.startTime, segment.startTime - 600) - 60, end: segment.startTime + 120),
                                selectedTime: segment.startTime,
                                searchText: searchText,
                                isSameTime: isSameTime,
                                onSelect: { viewModel.updateSegmentBoundary(at: currentIndex, newTime: $0, isStart: true) }
                            )
                        }
                        .frame(maxHeight: .infinity)
                    } else {
                        // Regular modes: Single ScrollView
                        ScrollView {
                            VStack(alignment: .leading, spacing: 20) {
                                if viewModel.config.validationMode == .text {
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
                    }
                }
                .onAppear {
                    viewModel.markAsViewed(id: segment.id)
                }
                .id(segment.id)
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
    
    private func getBlocksInRange(start: TimeInterval, end: TimeInterval) -> [SRTBlock] {
        let adjustedStart = start - viewModel.config.timeOffset
        let adjustedEnd = end - viewModel.config.timeOffset
        return viewModel.srtBlocks.filter {
            $0.endTime >= adjustedStart && $0.startTime <= adjustedEnd
        }
    }
}
