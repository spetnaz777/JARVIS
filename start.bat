@echo off
title JARVIS AI Assistant
color 0B

echo.
echo  ============================================================
echo   JARVIS - Just A Rather Very Intelligent System
echo  ============================================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo  [ERROR] .env file not found.
    echo  Please copy .env.example to .env and add your ANTHROPIC_API_KEY
    echo.
    pause
    exit /b 1
)

REM Start backend
echo  [1/2] Starting JARVIS Backend...
cd backend
start /B cmd /c "python main.py > ..\logs\backend.log 2>&1"
cd ..

REM Wait for backend to initialize
echo  [   ] Waiting for backend to start...
timeout /t 4 /nobreak > nul

REM Check if backend is running
curl -s http://localhost:8000/api/health > nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARN] Backend may still be initializing...
    timeout /t 3 /nobreak > nul
)

echo  [2/2] Starting JARVIS Frontend...
cd frontend
start /B cmd /c "npm start > ..\logs\frontend.log 2>&1"
cd ..

echo.
echo  ============================================================
echo   JARVIS is starting up!
echo.
echo   - Voice activation:  Ctrl+Shift+Space
echo   - Hide/show window:  Ctrl+Shift+H
echo   - Backend API:       http://localhost:8000
echo   - API docs:          http://localhost:8000/docs
echo.
echo   Logs: logs\backend.log and logs\frontend.log
echo  ============================================================
echo.
echo  Press any key to stop JARVIS...
pause > nul

echo  Stopping JARVIS...
taskkill /F /IM python.exe /T > nul 2>&1
taskkill /F /IM node.exe /T > nul 2>&1
taskkill /F /IM electron.exe /T > nul 2>&1
echo  JARVIS stopped.
