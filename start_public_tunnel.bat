@echo off
title ForteBank AI Datathon - BIG4 Team Server & Tunnel
echo ========================================================
echo   TEAM BIG4 - ForteBank Datathon '26 AI Service
echo ========================================================
echo.
echo Starting FastAPI Backend on port 8000...
start "Backend Server" cmd /k "python run_backend.py"
echo Waiting 3 seconds for server to initialize...
timeout /t 3 /nobreak >nul
echo.
echo Starting Public Cloudflare Tunnel...
.\cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
