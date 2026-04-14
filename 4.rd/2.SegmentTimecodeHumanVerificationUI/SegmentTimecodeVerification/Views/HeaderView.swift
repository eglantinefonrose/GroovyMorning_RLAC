import SwiftUI

struct HeaderView: View {
    @ObservedObject var viewModel: AppViewModel
    
    var body: some View {
        HStack(spacing: 20) {
            Picker("Media File", selection: $viewModel.selectedMediaURL) {
                Text("Select a file").tag(nil as URL?)
                ForEach(viewModel.availableMediaFiles, id: \.self) { url in
                    Text(url.lastPathComponent).tag(url as URL?)
                }
            }
            .frame(width: 300)
            
            HStack {
                Text("Start X:")
                TextField("X", value: $viewModel.config.defaultXSeconds, formatter: NumberFormatter())
                    .frame(width: 40)
                    .textFieldStyle(.roundedBorder)
                Text("s")
            }
            
            HStack {
                Text("End Y:")
                TextField("Y", value: $viewModel.config.defaultYSeconds, formatter: NumberFormatter())
                    .frame(width: 40)
                    .textFieldStyle(.roundedBorder)
                Text("s")
            }
            
            Toggle("Autoplay", isOn: $viewModel.config.autoPlay)
            
            Picker("Mode", selection: $viewModel.config.validationMode) {
                ForEach(ValidationMode.allCases, id: \.self) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 120)
            
            Divider().frame(height: 20)
            
            Toggle(isOn: $viewModel.isEditingMode) {
                Label("Edit Mode", systemImage: "pencil.and.outline")
            }
            .toggleStyle(.button)
            .help("Toggle edit mode (Space)")
            
            Divider().frame(height: 20)
            
            HStack(spacing: 10) {
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
                    Label("Preview (L)", systemImage: "play.circle")
                }
            }
            
            Spacer()
            
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectDirectory { path in
                        viewModel.config.mediaDirectoryPath = path
                        viewModel.saveConfig()
                        viewModel.refreshMediaFiles()
                    }
                } label: {
                    Label("Media Folder", systemImage: "folder.fill")
                }
                if let path = viewModel.config.mediaDirectoryPath {
                    Text(URL(fileURLWithPath: path).lastPathComponent).font(.system(size: 9)).foregroundColor(.secondary)
                }
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectDirectory { path in
                        viewModel.config.transcriptionDirectoryPath = path
                        viewModel.saveConfig()
                    }
                } label: {
                    Label("SRT Folder", systemImage: "captions.bubble.fill")
                }
                if let path = viewModel.config.transcriptionDirectoryPath {
                    Text(URL(fileURLWithPath: path).lastPathComponent).font(.system(size: 9)).foregroundColor(.secondary)
                }
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Button {
                    selectDirectory { path in
                        viewModel.config.timecodeDirectoryPath = path
                        viewModel.saveConfig()
                    }
                } label: {
                    Label("TXT Folder", systemImage: "doc.text.fill")
                }
                if let path = viewModel.config.timecodeDirectoryPath {
                    Text(URL(fileURLWithPath: path).lastPathComponent).font(.system(size: 9)).foregroundColor(.secondary)
                }
            }
        }
        .buttonStyle(.bordered)
        .padding()
        .background(Color(NSColor.windowBackgroundColor))
    }
    
    private func selectDirectory(completion: @escaping (String) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                completion(url.path)
            }
        }
    }
}
