import SwiftUI

struct ContentView: View {
    @StateObject var viewModel = AppViewModel()
    
    var body: some View {
        NavigationSplitView {
            SegmentListView(viewModel: viewModel)
        } detail: {
            VStack(spacing: 0) {
                HeaderView(viewModel: viewModel)
                TranscriptionView(viewModel: viewModel)
            }
        }
        .onAppear {
            // Initial setup if needed
        }
        .focusable()
        .onKeyPress(.downArrow) {
            viewModel.selectNextSegment()
            return .handled
        }
        .onKeyPress(.upArrow) {
            viewModel.selectPreviousSegment()
            return .handled
        }
        .onKeyPress(.space) {
            viewModel.toggleEditMode()
            return .handled
        }
        .onKeyPress { keyPress in
            if keyPress.characters == "l" {
                viewModel.playCurrentSegment()
                return .handled
            }
            if keyPress.characters == "s" {
                viewModel.saveSegments()
                return .handled
            }
            return .ignored
        }
    }
}
