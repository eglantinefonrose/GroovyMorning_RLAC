import SwiftUI
import UniformTypeIdentifiers

struct SegmentListView: View {
    @ObservedObject var viewModel: AppViewModel
    @State private var editingId: UUID?
    @State private var editingTitle: String = ""
    @FocusState private var isRenameFocused: Bool

    var body: some View {
        VStack {
            if viewModel.availableMediaFiles.isEmpty {
                ContentUnavailableView("No Media Files", systemImage: "music.note.list", description: Text("Set the media folder and ensure it contains .mp3 files."))
            } else if viewModel.selectedMediaURL == nil {
                ContentUnavailableView("No Media Selected", systemImage: "play.circle", description: Text("Select a media file from the dropdown above."))
            } else {
                ScrollViewReader { proxy in
                    List(selection: $viewModel.selectedSegmentId) {
                        if viewModel.segments.isEmpty {
                            ContentUnavailableView {
                                Label("No Segments Found", systemImage: "text.badge.xmark")
                            } description: {
                                Text("Could not find a .txt file matching this audio.")
                            } actions: {
                                Button("Select TXT Manually") {
                                    selectFile(extensions: ["txt"]) { url in
                                        viewModel.loadManualTXT(url: url)
                                    }
                                }
                            }
                        } else {
                            ForEach(viewModel.segments) { segment in
                                HStack {
                                    VStack(alignment: .leading) {
                                        if editingId == segment.id {
                                            TextField("Titre", text: $editingTitle, onCommit: {
                                                viewModel.renameSegment(id: segment.id, newTitle: editingTitle)
                                                editingId = nil
                                            })
                                            .focused($isRenameFocused)
                                            .textFieldStyle(.roundedBorder)
                                        } else {
                                            Text(segment.title)
                                                .font(.headline)
                                            Text("\(formatTime(segment.startTime)) - \(formatTime(segment.endTime))")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
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
                                .padding(.vertical, 4)
                                .contentShape(Rectangle())
                                .tag(segment.id as UUID?)
                                .onTapGesture {
                                    viewModel.selectedSegmentId = segment.id
                                }
                                .contextMenu {
                                    Button("Renommer") {
                                        startEditing(segment)
                                    }
                                    Button(role: .destructive) {
                                        if let index = viewModel.segments.firstIndex(where: { $0.id == segment.id }) {
                                            viewModel.deleteSegment(at: index)
                                        }
                                    } label: {
                                        Label("Supprimer", systemImage: "trash")
                                    }
                                }
                            }
                            .onDelete { indexSet in
                                for index in indexSet {
                                    viewModel.deleteSegment(at: index)
                                }
                            }
                        }
                    }
                    .onKeyPress(.return) {
                        if let id = viewModel.selectedSegmentId,
                           let segment = viewModel.segments.first(where: { $0.id == id }) {
                            startEditing(segment)
                            return .handled
                        }
                        return .ignored
                    }
                    .onChange(of: viewModel.selectedSegmentId) { _, newValue in
                        if let id = newValue {
                            withAnimation {
                                proxy.scrollTo(id, anchor: .center)
                            }
                        }
                    }
                }
            }
        }
        .frame(minWidth: 250)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    viewModel.createNewSegment()
                } label: {
                    Label("Add Chronique", systemImage: "plus")
                }
                .disabled(viewModel.selectedMediaURL == nil)
            }
        }
    }
    
    private func startEditing(_ segment: Segment) {
        editingTitle = segment.title
        editingId = segment.id
        isRenameFocused = true
    }
    
    private func formatTime(_ time: TimeInterval) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        return String(format: "%02d:%02d", minutes, seconds)
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
}
