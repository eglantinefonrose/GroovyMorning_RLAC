import time
import requests
import os
import subprocess

JAVA_API_URL = os.environ.get('JAVA_API_URL', 'http://backend-java:8000')
PYTHON_API_URL = os.environ.get('PYTHON_API_URL', 'http://python-api:8001')
TEST_FLUX_WAV = "e2e/assets/test_flux.wav"
AUDIO_PIPE = "/tmp/audio_pipe"

def wait_for_service(url, name):
    print(f"⏳ Waiting for {name} at {url}...")
    for _ in range(30):
        try:
            resp = requests.get(f"{url}/api/status")
            if resp.status_code == 200:
                print(f"✅ {name} is ready!")
                return True
        except:
            pass
        time.sleep(2)
    print(f"❌ {name} timed out!")
    return False

def run_e2e():
    # 1. Wait for services
    if not wait_for_service(PYTHON_API_URL, "Python API"): return
    if not wait_for_service(JAVA_API_URL, "Java Backend"): return

    # 2. Get localUserId
    print("👤 Getting localUserId...")
    try:
        resp = requests.get(f"{JAVA_API_URL}/api/getUserBaseTime")
        user_id = resp.json().get('userId')
        print(f"✅ localUserId: {user_id}")
    except Exception as e:
        print(f"❌ Could not get localUserId: {e}")
        return

    # 3. Add chronicle if missing
    print(f"📝 Ensuring chronicle 'journal de 7h' is authorized for {user_id}...")
    requests.post(f"{JAVA_API_URL}/api/addChronicle", params={
        "nomDeChroniques": "journal de 7h",
        "chroniqueRealTimecode": 0,
        "duration": 300
    })

    # 4. Prepare the audio pipes
    for pipe in [AUDIO_PIPE, "/tmp/audio_pipe_java"]:
        if not os.path.exists(pipe):
            os.mkfifo(pipe)

    print(f"🚀 Feeding audio flux {TEST_FLUX_WAV} to pipes...")
    
    # We use a background process to feed both pipes
    feeder = subprocess.Popen(f"cat {TEST_FLUX_WAV} | tee {AUDIO_PIPE} > /tmp/audio_pipe_java", shell=True)

    # 5. Wait for detection and recording
    print("⏳ Waiting for chronicle detection and recording (30s)...")
    time.sleep(30)

    # 6. Verify results via Java API
    print("🔍 Verifying results via Java API...")
    try:
        resp = requests.get(f"{JAVA_API_URL}/api/getUserChronicles")
        chronicles = resp.json()
        print(f"📊 Recorded chronicles for {user_id}: {chronicles}")
        
        # Check if 'journal de 7h' is in the list
        found = any(c.get('nomDeChronique') == 'journal de 7h' for c in chronicles)
        if found:
            print("✨ SUCCESS: 'journal de 7h' was detected and recorded!")
        else:
            print("❌ FAILURE: 'journal de 7h' not found in Java Backend.")
            exit(1)
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        exit(1)

    print("🏁 E2E Test Completed.")

if __name__ == "__main__":
    run_e2e()
