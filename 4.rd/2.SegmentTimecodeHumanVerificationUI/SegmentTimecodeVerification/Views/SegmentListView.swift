import SwiftUI

struct SegmentListView: View {
    @ObservedObject var viewModel: AppViewModel
    
    var body: some View {
        VStack {
            if viewModel.availableMediaFiles.isEmpty {
                ContentUnavailableView("No Media Files", systemImage: "music.note.list", description: Text("Set the media folder and ensure it contains .mp3 files."))
            } else if viewModel.selectedMediaURL == nil {
                ContentUnavailableView("No Media Selected", systemImage: "play.circle", description: Text("Select a media file from the dropdown above."))
            } else if viewModel.segments.isEmpty {
                ContentUnavailableView("No Segments Found", systemImage: "text.badge.xmark", description: Text("Could not find or parse segments in the .txt file."))
            } else {
                List(selection: $viewModel.selectedSegmentIndex) {
                    ForEach(0..<viewModel.segments.count, id: \.self) { index in
                        let segment = viewModel.segments[index]
                        HStack {
                            VStack(alignment: .leading) {
                                Text(segment.title)
                                    .font(.headline)
                                Text("\(formatTime(segment.startTime)) - \(formatTime(segment.endTime))")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            if segment.isModified {
                                Circle()
                                    .fill(Color.orange)
                                    .frame(width: 8, height: 8)
                            } else if segment.isViewed {
                                Circle()
                                    .fill(Color.green)
                                    .frame(width: 8, height: 8)
                            }
                        }
                        .tag(index as Int?)
                    }
                }
            }
        }
        .frame(minWidth: 250)
    }
    
    private func formatTime(_ time: TimeInterval) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }
}
