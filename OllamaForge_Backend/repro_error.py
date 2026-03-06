import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_chat():
    # 1. Init Session
    print("Initializing session...")
    res = requests.post(f"{BASE_URL}/api/init_session", json={"session_id": "test_session"})
    print("Init Session response:", res.json())

    # 2. Set Model
    print("Setting model...")
    res = requests.post(f"{BASE_URL}/api/set_model", json={"session_id": "test_session", "model": "llama3"})
    print("Set Model response:", res.json())

    # 3. Chat (Non-streaming)
    print("Sending chat request (non-streaming)...")
    payload = {
        "session_id": "test_session",
        "message": "Hello, how are you?",
        "stream": False
    }
    try:
        res = requests.post(f"{BASE_URL}/api/chat", json=payload)
        print("Status Code:", res.status_code)
        if res.status_code == 200:
            print("Response:", res.json())
        else:
            print("Error Response:", res.text)
    except Exception as e:
        print("Request failed:", e)

if __name__ == "__main__":
    test_chat()
