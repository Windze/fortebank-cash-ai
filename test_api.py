import time
import glob
import os
from fastapi.testclient import TestClient
import backend.config as config
from backend.main import app

def test_api():
    client = TestClient(app)

    print("--- 1. Testing Root and Health Endpoints ---")
    res = client.get("/")
    assert res.status_code == 200
    print("GET / -> Status 200 (HTML Web App loaded)")

    res = client.get("/health")
    assert res.status_code == 200
    print("GET /health ->", res.json())

    print("\n--- 2. Testing Authorization (X-API-Key) ---")
    res = client.post(
        "/api/v1/analyze",
        files={"file": ("test.mov", b"dummy", "video/quicktime")}
    )
    print("Without API Key -> Status:", res.status_code)
    assert res.status_code == 401

    res = client.post(
        "/api/v1/analyze",
        headers={"X-API-Key": "wrong-key"},
        files={"file": ("test.mov", b"dummy", "video/quicktime")}
    )
    print("With wrong API Key -> Status:", res.status_code)
    assert res.status_code == 401

    print("\n--- 3. Testing POST /api/v1/analyze with sample video ---")
    candidates = glob.glob("open/videos/*.mov")
    if not candidates:
        print("No .mov videos found!")
        return

    sample_video = candidates[0]
    print(f"Uploading file: {os.path.basename(sample_video)} ({os.path.getsize(sample_video)} bytes)...")

    with open(sample_video, "rb") as f:
        res = client.post(
            "/api/v1/analyze",
            headers={"X-API-Key": config.API_KEY},
            files={"file": (os.path.basename(sample_video), f, "video/quicktime")}
        )

    print("POST /api/v1/analyze Response status:", res.status_code)
    print("POST /api/v1/analyze Response body:", res.json())
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id is not None

    print(f"\n--- 4. Polling GET /api/v1/jobs/{job_id} ---")
    for i in range(30):
        res = client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"X-API-Key": config.API_KEY}
        )
        data = res.json()
        status = data.get("status")
        print(f"Poll #{i+1}: status={status}")
        if status == "done":
            print("\nAnalysis Finished Successfully!")
            print(f"Verdict: {data.get('verdict')}")
            print(f"Violations count: {len(data.get('violations', []))}")
            for v in data.get("violations", []):
                print(f"  - [{v['timecode_sec']}s] {v['type']}")
                print(f"    Evidence frames: {len(v['evidence_frames'])}")
                print(f"    Description: {v['description'][:80]}...")
            break
        elif status == "failed":
            print("Job failed:", data.get("error"))
            break
        time.sleep(1.0)

if __name__ == "__main__":
    test_api()
