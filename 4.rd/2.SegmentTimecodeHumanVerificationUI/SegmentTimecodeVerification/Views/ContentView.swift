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
            if viewModel.isShowingAddSegment { return .ignored }
            viewModel.selectNextSegment()
            return .handled
        }
        .onKeyPress(.upArrow) {
            if viewModel.isShowingAddSegment { return .ignored }
            viewModel.selectPreviousSegment()
            return .handled
        }
        .onKeyPress { keyPress in
            if viewModel.isShowingAddSegment { return .ignored }
            
            if keyPress.characters == "s" {
                viewModel.saveSegments()
                return .handled
            }
            if keyPress.key == .delete {
                if let index = viewModel.selectedSegmentIndex {
                    viewModel.deleteSegment(at: index)
                    return .handled
                }
            }
            return .ignored
        }
    }
}
