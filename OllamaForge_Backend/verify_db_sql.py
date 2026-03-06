import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_database_chat():
    # Assume a database is already connected or we use 'Direct Chat' if it's easier to mock
    # But the user specifically has issue with 'Database' source.
    # Let's try to set source to Database.
    
    session_id = "test_session_db"
    
    print(f"Initializing session {session_id}...")
    requests.post(f"{BASE_URL}/api/init_session", json={"session_id": session_id})
    
    print("Setting model...")
    requests.post(f"{BASE_URL}/api/set_model", json={"session_id": session_id, "model": "llama3"})
    
    print("Setting source to Database...")
    requests.post(f"{BASE_URL}/api/set_source", json={"session_id": session_id, "source": "Database"})
    
    # We need a db_path. Let's use the one from the screenshot or a known local one.
    # From earlier list_dir, mydatabase.db exists.
    db_path = "d:/OllamaForge_Backend/mydatabase.db"
    print(f"Initializing database {db_path}...")
    requests.post(f"{BASE_URL}/api/init_database", json={"session_id": session_id, "db_path": db_path})

    print("Sending complex database query...")
    payload = {
        "session_id": session_id,
        "message": "summarize the information about the given database.",
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
    test_database_chat()
