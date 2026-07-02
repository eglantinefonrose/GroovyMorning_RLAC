import chromaprint
import acoustid
import numpy as np

def test_fingerprint():
    try:
        sample_rate = 16000
        # 1 second of noise
        pcm_data = (np.random.randn(sample_rate) * 32768).astype(np.int16).tobytes()
        duration, fp = acoustid.fingerprint(sample_rate, 1, pcm_data)
        print(f"Fingerprint generated successfully! Duration: {duration}")
    except NameError as e:
        print(f"NameError: {e}")
    except Exception as e:
        print(f"Other Error: {e}")

if __name__ == "__main__":
    test_fingerprint()
