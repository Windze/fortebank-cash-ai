import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security & API Settings
API_KEY = os.getenv("API_KEY", "forte-datathon-2026-key")

# Directories
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Model Settings
# yolov8s.pt is in the project root
MODEL_PATH = os.path.join(BASE_DIR, "yolov8s.pt")
POSE_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n-pose.pt")

# Detection Parameters
SAMPLE_FPS = 2.0  # Sample 2 frames per second for high-speed analysis
CONF_THRESHOLD = 0.25
MAX_PROCESS_TIME_SEC = 290  # Well within the 5-minute (300s) timeout
