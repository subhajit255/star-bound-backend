import requests
import time
import os
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def run_test():
    session = requests.Session()
    
    # 1. Register and Login to get a token
    print("\n--- 1. Authenticating ---")
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = session.post(f"{BASE_URL}/auth/register", json={
        "name": "E2E Test User",
        "email": email,
        "password": "password123"
    })
    
    if reg_res.status_code != 201:
        print("Registration failed, trying login...")
        log_res = session.post(f"{BASE_URL}/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        token = log_res.json().get("access_token")
    else:
        token = reg_res.json().get("access_token")
        
    if not token:
        print("Failed to authenticate. Exiting.")
        return
        
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"Authenticated as {email}")
    
    # 2. Upload Image
    print("\n--- 2. Uploading Image ---")
    image_path = "test_images/mole.jpg"
    if not os.path.exists(image_path):
        print(f"Cannot find {image_path}. Please create a dummy image there.")
        return
        
    with open(image_path, "rb") as f:
        files = {"image": ("mole.jpg", f, "image/jpeg")}
        up_res = session.post(f"{BASE_URL}/uploads/", files=files)
        
    if up_res.status_code != 201:
        print(f"Upload failed: {up_res.text}")
        return
        
    upload_data = up_res.json()
    upload_id = upload_data["upload_id"]
    print(f"Upload successful. Upload ID: {upload_id}")
    
    # 3. Trigger Analysis
    print("\n--- 3. Triggering Analysis ---")
    an_res = session.post(f"{BASE_URL}/analyses/", json={"uploadId": upload_id})
    if an_res.status_code != 200:
        print(f"Analysis trigger failed: {an_res.text}")
        return
        
    analysis_id = an_res.json()["analysis_id"]
    print(f"Analysis triggered. Analysis ID: {analysis_id}")
    
    # 4. Poll for Detection Completion
    print("\n--- 4. Polling Analysis Status (Make sure Celery is running!) ---")
    for i in range(15):
        poll_res = session.get(f"{BASE_URL}/analyses/{analysis_id}")
        status = poll_res.json().get("status")
        print(f"Polling... Status: {status}")
        if status in ["success", "failed"]:
            break
        time.sleep(2)
        
    if status != "success":
        print("Detection did not succeed in time.")
        return
        
    print(f"Detection results: {poll_res.json().get('n_points')} points found natively.")
    
    # 5. Patch Points (Mocking user adding 4 points so we can force a match)
    print("\n--- 5. Patching Points to Force a Match ---")
    # We provide 4 dummy points in a roughly square shape which should yield a match attempt
    patch_data = {
        "points": [
            {"x": 100.0, "y": 100.0, "radius": 5.0, "score": 1.0, "source": "user_added"},
            {"x": 200.0, "y": 100.0, "radius": 5.0, "score": 1.0, "source": "user_added"},
            {"x": 100.0, "y": 200.0, "radius": 5.0, "score": 1.0, "source": "user_added"},
            {"x": 250.0, "y": 250.0, "radius": 5.0, "score": 1.0, "source": "user_added"},
        ]
    }
    patch_res = session.patch(f"{BASE_URL}/analyses/{analysis_id}/points", json=patch_data)
    print(f"Patch response: {patch_res.status_code} - {patch_res.json().get('status')}")
    
    # 6. Poll for Matching Completion
    print("\n--- 6. Polling Matching Status ---")
    for i in range(15):
        poll_res = session.get(f"{BASE_URL}/analyses/{analysis_id}")
        status = poll_res.json().get("status")
        print(f"Polling... Status: {status}")
        if status in ["success", "failed"]:
            break
        time.sleep(2)
        
    # 7. Fetch Skymap
    print("\n--- 7. Fetching Skymap ---")
    skymap_res = session.get(f"{BASE_URL}/skymap/{analysis_id}/skymap")
    if skymap_res.status_code == 200:
        print("Skymap Output:")
        print(skymap_res.json())
    else:
        print(f"Failed to fetch skymap: {skymap_res.text}")

if __name__ == "__main__":
    run_test()
