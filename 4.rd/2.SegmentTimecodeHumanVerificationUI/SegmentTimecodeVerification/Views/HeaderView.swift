import SwiftUI
import UniformTypeIdentifiers

struct HeaderView: View {
    @ObservedObject var viewModel: AppViewModel
    
    var body: some View {
        HStack(spacing: 15) {
            // Media Selection
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectFile(extensions: ["mp3", "wav", "m4a"]) { url in
                        viewModel.selectedMediaURL = url
                    }
                } label: {
                    Label(viewModel.selectedMediaURL?.lastPathComponent ?? "Open Audio", systemImage: "music.note")
                }
                .buttonStyle(.borderedProminent)
            }
            
            // SRT Selection
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectFile(extensions: ["srt"]) { url in
                        viewModel.selectedSRTURL = url
                    }
                } label: {
                    Label(viewModel.selectedSRTURL?.lastPathComponent ?? "Open SRT", systemImage: "captions.bubble")
                }
            }
            
            // TXT Selection
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectFile(extensions: ["txt"]) { url in
                        viewModel.selectedTXTURL = url
                    }
                } label: {
                    Label(viewModel.selectedTXTURL?.lastPathComponent ?? "Open TXT", systemImage: "doc.text")
                }
            }

            Divider().frame(height: 30)

            // Settings
            Group {
                HStack(spacing: 5) {
                    Text("X:")
                    TextField("X", value: $viewModel.config.defaultXSeconds, formatter: NumberFormatter())
                        .frame(width: 35)
                        .textFieldStyle(.roundedBorder)
                    Text("s")
                }
                
                HStack(spacing: 5) {
                    Text("Y:")
                    TextField("Y", value: $viewModel.config.defaultYSeconds, formatter: NumberFormatter())
                        .frame(width: 35)
                        .textFieldStyle(.roundedBorder)
                    Text("s")
                }
                
                Toggle("Auto", isOn: $viewModel.config.autoPlay)
                    .toggleStyle(.checkbox)
            }
            
            Picker("Mode", selection: $viewModel.config.validationMode) {
                ForEach(ValidationMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 100)
            
            Divider().frame(height: 30)
            
            Toggle(isOn: $viewModel.isEditingMode) {
                Image(systemName: "pencil.and.outline")
            }
            .toggleStyle(.button)
            .help("Toggle edit mode")
            
            HStack(spacing: 5) {
                Button {
                    if viewModel.audioPlayer.isPlaying {
                        viewModel.audioPlayer.pause()
                    } else {
                        viewModel.audioPlayer.play()
                    }
                } label: {
                    Image(systemName: viewModel.audioPlayer.isPlaying ? "pause.fill" : "play.fill")
                }
                
                Button {
                    viewModel.playCurrentSegment()
                } label: {
                    Image(systemName: "play.circle")
                }
                .help("Preview segment")
            }
            
            Spacer()
        }
        .buttonStyle(.bordered)
        .padding(10)
        .background(Color(NSColor.windowBackgroundColor))
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

