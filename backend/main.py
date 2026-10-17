import os
import uuid
import shutil
import traceback
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import backend.config as config
from backend.schemas import AnalyzeInitResponse, JobResponse
from backend.database import job_store
from backend.detector import VideoAnalyzer
from backend.rules_kb import RULES_REGISTRY

app = FastAPI(
    title="ForteBank Cash Desk Discipline AI Service",
    description="AI-сервис для автоматического выявления нарушений кассовой дисциплины по видеозаписям для Datathon 26",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton analyzer instance
analyzer = VideoAnalyzer()

# Mount Static Directories
FRONTEND_DIR = os.path.join(config.BASE_DIR, "frontend")
VIDEOS_DIR = os.path.join(config.BASE_DIR, "open", "videos")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if os.path.exists(VIDEOS_DIR):
    app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

def process_video_background(job_id: str, file_path: str):
    """Background task to analyze uploaded video file."""
    try:
        # Run detection pipeline
        analysis_result = analyzer.analyze_video(file_path)
        
        job_store.update_job(
            job_id,
            status="done",
            verdict=analysis_result["verdict"],
            violations=analysis_result["violations"]
        )
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] Job {job_id} failed: {error_msg}")
        job_store.update_job(
            job_id,
            status="failed",
            error=str(e)
        )

def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify jury API Key according to Section 10 of TZ."""
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствующий API-ключ в заголовке X-API-Key"
        )
    return x_api_key

@app.get("/")
def serve_index():
    """Serve the Datathon '26 themed web interface."""
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "service": "ForteBank Cash Desk Discipline AI Service",
        "status": "online",
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ready"}

@app.get("/api/v1/info")
def get_service_info():
    """Meta information on supported violations and regulatory rules."""
    return {
        "service": "ForteBank Cash Desk Discipline AI Inspector",
        "framework": "YOLOv8 + Spatial/Temporal Rule Engine",
        "supported_rules": RULES_REGISTRY
    }

@app.post(
    "/api/v1/analyze",
    response_model=AnalyzeInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Загрузить видео для анализа"
)
async def analyze_video_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Видеофайл кассы в формате .mov"),
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Шаг 1 API: Загрузить видео в формате .mov (поле file).
    В ответ немедленно возвращается job_id.
    """
    verify_api_key(x_api_key)

    filename = file.filename or "video.mov"
    if not (filename.lower().endswith(".mov") or filename.lower().endswith(".mp4")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неподдерживаемый формат файла. Требуется видеозапись в формате .mov"
        )

    job_id = uuid.uuid4().hex[:8]
    save_path = os.path.join(config.UPLOAD_DIR, f"{job_id}_{filename}")

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_store.create_job(job_id)
    background_tasks.add_task(process_video_background, job_id, save_path)

    return {"job_id": job_id}

@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    summary="Получить статус и результат обработки"
)
def get_job_status_endpoint(
    job_id: str,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Шаг 2 API: Получить статус обработки (processing, done, failed) и результат.
    """
    verify_api_key(x_api_key)

    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с job_id '{job_id}' не найдена"
        )

    response = {
        "job_id": job["job_id"],
        "status": job["status"]
    }

    if job["status"] == "done":
        response["verdict"] = job.get("verdict", "no_violation")
        response["violations"] = job.get("violations", [])
    elif job["status"] == "failed":
        response["error"] = job.get("error", "Processing error")

    return response
