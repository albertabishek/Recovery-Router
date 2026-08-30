@echo off
title Recovery Router - Shutdown
echo ============================================
echo  Recovery Router - Stopping All Services
echo ============================================
echo.

echo [1/3] Stopping Celery workers...
taskkill /f /fi "WINDOWTITLE eq Celery Worker*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Celery Beat*" >nul 2>&1
celery -A app.celery_app control shutdown >nul 2>&1
echo  Celery stopped.

echo [2/3] Stopping Uvicorn...
taskkill /f /fi "WINDOWTITLE eq Uvicorn API*" >nul 2>&1
echo  Uvicorn stopped.

echo [3/3] Redis left running (shared resource).
echo.

echo ============================================
echo  All services stopped.
echo  Events in Supabase are safe.
echo  Restart with: start.bat
echo ============================================
pause >nul
