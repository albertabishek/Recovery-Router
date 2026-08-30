@echo off
title Recovery Router - Startup
echo ============================================
echo  Recovery Router - Starting All Services
echo ============================================
echo.

REM Check if Redis is running
echo [1/4] Checking Redis...
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo  Redis not running. Starting Redis...
    start "Redis Server" redis-server
    timeout /t 3 /nobreak >nul
    redis-cli ping >nul 2>&1
    if %errorlevel% neq 0 (
        echo  ERROR: Redis failed to start. Install Redis or start it manually.
        pause
        exit /b 1
    )
)
echo  Redis is running.
echo.

REM Start Celery Worker
echo [2/4] Starting Celery Worker...
cd backend
start "Celery Worker" cmd /k "celery -A app.celery_app worker --pool=solo --concurrency=1 --loglevel=info"
timeout /t 2 /nobreak >nul
echo  Celery Worker started.
echo.

REM Start Celery Beat
echo [3/4] Starting Celery Beat...
start "Celery Beat" cmd /k "celery -A app.celery_app beat --loglevel=info"
timeout /t 2 /nobreak >nul
echo  Celery Beat started.
echo.

REM Start Uvicorn API Server
echo [4/4] Starting API Server...
start "Uvicorn API" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 2 /nobreak >nul
cd ..
echo  API Server started on http://localhost:8000
echo.

echo ============================================
echo  All services started successfully!
echo  - Redis:        localhost:6379
echo  - API Server:   http://localhost:8000
echo  - Celery Worker: processing tasks
echo  - Celery Beat:   scheduling every 5 min
echo ============================================
echo.
echo  Frontend: cd frontend ^&^& npm run dev
echo.
echo  Press any key to exit this window...
echo  (Services will keep running in their own windows)
pause >nul
