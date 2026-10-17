import uvicorn
import backend.config as config

if __name__ == "__main__":
    print(f"==================================================")
    print(f" ForteBank Cash Desk Discipline AI Service")
    print(f" API Key: {config.API_KEY}")
    print(f" Swagger UI: http://localhost:8000/docs")
    print(f" API Endpoint: http://localhost:8000/api/v1/analyze")
    print(f"==================================================")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
