import time
import os
import tempfile
from pydub import AudioSegment

class AudioSimulator:
    def __init__(self, audio_path, buffer_size_seconds=5):
        self.audio_path = audio_path
        self.buffer_size_seconds = buffer_size_seconds
        
    def simulate(self, method_wrapper, window_size_seconds=300):
        """
        Simulates a live stream by slicing the audio file into a sliding window.
        Default window size is 300s (5 min) to cover most radio chronicles.
        """
        print(f"Starting LIVE simulation (sliding window: {window_size_seconds}s) for {self.audio_path}...")
        
        if not os.path.exists(self.audio_path):
            print(f"Error: Audio file {self.audio_path} not found.")
            return []

        # Load the full audio to simulate the stream
        try:
            full_audio = AudioSegment.from_file(self.audio_path)
        except Exception as e:
            print(f"Error loading audio with pydub: {e}. Falling back to batch mode.")
            return method_wrapper.process_stream(self.audio_path, self.buffer_size_seconds)

        duration_ms = len(full_audio)
        duration_secs = duration_ms / 1000.0
        
        all_detections = []
        known_detection_ids = set()
        
        # We simulate the passing of time in chunks
        for current_time_ms in range(0, duration_ms, self.buffer_size_seconds * 1000):
            end_time_ms = min(current_time_ms + self.buffer_size_seconds * 1000, duration_ms)
            current_time_secs = end_time_ms / 1000.0
            
            # Window calculation (to avoid processing the whole file every time)
            start_ms = max(0, end_time_ms - (window_size_seconds * 1000))
            offset_secs = start_ms / 1000.0
            
            print(f"--- Live Diffusion: {current_time_secs:.1f}s / {duration_secs:.1f}s (window: {offset_secs:.1f}s-{current_time_secs:.1f}s) ---")
            
            live_buffer = full_audio[start_ms:end_time_ms]
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_path = temp_audio.name
                live_buffer.export(temp_path, format="wav")
            
            try:
                # Call the wrapper on the current "live" window
                detections = method_wrapper.process_stream(temp_path, self.buffer_size_seconds)
                
                for d in detections:
                    # Re-align timestamps with the global timeline
                    d['start'] = round(d['start'] + offset_secs, 2)
                    d['end'] = round(d['end'] + offset_secs, 2)
                    
                    det_id = f"{d['start']:.2f}-{d['end']:.2f}-{d.get('label', '')}"
                    
                    if det_id not in known_detection_ids:
                        # In live, we only accept detections that are completed in the current window
                        # We use a small margin (0.5s) for float precision.
                        if d['end'] <= current_time_secs + 0.5:
                            print(f"  [LIVE DETECTED] {d.get('label', 'chronique')} at {d['start']:.2f}s - {d['end']:.2f}s")
                            d['detected_at'] = current_time_secs
                            all_detections.append(d)
                            known_detection_ids.add(det_id)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        return all_detections

# If we want a more realistic simulator that actually controls the timing:
class RealTimeSimulator:
    def __init__(self, audio_duration, speed_factor=1.0):
        self.audio_duration = audio_duration
        self.speed_factor = speed_factor # 1.0 = real time, 10.0 = 10x faster

    def run(self, method_process_func):
        # Implementation would involve a loop and sleep
        pass
