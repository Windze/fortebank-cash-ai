import time
import threading
from typing import Dict, Any, Optional

class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            record = {
                "job_id": job_id,
                "status": "processing",
                "verdict": None,
                "violations": [],
                "error": None,
                "created_at": time.time(),
                "finished_at": None
            }
            self._jobs[job_id] = record
            return record

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return dict(job)
            return None

    def update_job(self, job_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for k, v in kwargs.items():
                job[k] = v
            if kwargs.get("status") in ("done", "failed"):
                job["finished_at"] = time.time()
            return dict(job)

# Global singleton instance
job_store = JobStore()
