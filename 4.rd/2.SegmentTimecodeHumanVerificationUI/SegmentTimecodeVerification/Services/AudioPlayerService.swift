import Foundation
import AVFoundation

@MainActor
class AudioPlayerService: ObservableObject {
    @Published var isPlaying = false
    @Published var currentTime: TimeInterval = 0
    
    private var player: AVPlayer?
    private var timeObserver: Any?
    private var playbackTimer: Timer?
    
    func load(url: URL) {
        player = AVPlayer(url: url)
        setupObserver()
    }
    
    private func setupObserver() {
        if let observer = timeObserver {
            player?.removeTimeObserver(observer)
        }
        
        timeObserver = player?.addPeriodicTimeObserver(forInterval: CMTime(seconds: 0.1, preferredTimescale: 600), queue: .main) { [weak self] time in
            Task { @MainActor in
                self?.currentTime = time.seconds
            }
        }
    }
    
    func playPreview(segment: Segment, x: Int, y: Int) {
        guard let player = player else { return }
        
        let startTime = segment.startTime
        let endTime = segment.endTime
        let xDuration = Double(x)
        let yDuration = Double(y)
        
        playbackTimer?.invalidate()
        
        // Play first X seconds
        player.seek(to: CMTime(seconds: startTime, preferredTimescale: 600))
        player.play()
        isPlaying = true
        
        playbackTimer = Timer.scheduledTimer(withTimeInterval: xDuration, repeats: false) { [weak self] _ in
            // Jump to end - Y
            let jumpTime = max(startTime, endTime - yDuration)
            player.seek(to: CMTime(seconds: jumpTime, preferredTimescale: 600))
            
            let innerTimer = Timer.scheduledTimer(withTimeInterval: yDuration, repeats: false) { [weak self] _ in
                Task { @MainActor in
                    player.pause()
                    self?.isPlaying = false
                }
            }
            
            Task { @MainActor in
                self?.playbackTimer = innerTimer
            }
        }
    }
    
    func play() {
        player?.play()
        isPlaying = true
    }
    
    func pause() {
        player?.pause()
        isPlaying = false
    }
    
    func stop() {
        player?.pause()
        isPlaying = false
        playbackTimer?.invalidate()
    }
    
    func seek(to time: TimeInterval) {
        player?.seek(to: CMTime(seconds: time, preferredTimescale: 600))
    }
}
