@echo off
title JARVIS — Starting Up
color 0B
cls

echo.
echo  ============================================================
echo   J.A.R.V.I.S  —  Just A Rather Very Intelligent System
echo  ============================================================
echo.

REM ── Kill any leftover processes from a previous session ──────────────────
taskkill /F /FI "WINDOWTITLE eq JARVIS Backend*" > nul 2>&1
taskkill /F /FI "WINDOWTITLE eq JARVIS Frontend*" > nul 2>&1
timeout /t 1 /nobreak > nul

REM ── Step 1: Start Python backend ─────────────────────────────────────────
echo  [1/3] Starting AI backend...
start "JARVIS Backend" /MIN cmd /k "cd /d "%~dp0backend" && python main.py"

REM ── Step 2: Wait until backend responds ──────────────────────────────────
echo  [2/3] Waiting for backend to come online...
set /a ATTEMPTS=0
:WAIT
timeout /t 1 /nobreak > nul
set /a ATTEMPTS+=1
curl -s http://127.0.0.1:8000/api/health > nul 2>&1
if %errorlevel% equ 0 goto READY
if %ATTEMPTS% lss 30 goto WAIT
echo  [WARN] Backend took too long — check the JARVIS Backend window for errors.
goto LAUNCH_FRONTEND

:READY
echo  [OK]  Backend is online.

REM ── Step 3: Launch the Electron HUD ──────────────────────────────────────
:LAUNCH_FRONTEND
echo  [3/3] Opening JARVIS window...
start "JARVIS Frontend" /MIN cmd /k "cd /d "%~dp0frontend" && npm start"

echo.
echo  ============================================================
echo   JARVIS is launching — the HUD window will appear shortly.
echo.
echo   CONTROLS:
echo     Ctrl+Shift+Space  →  Activate / stop voice input
echo     Ctrl+Shift+H      →  Hide / show window
echo     Type in the box   →  Text chat
echo.
echo   This console window can be safely closed after the HUD
echo   appears. To stop JARVIS fully, close the Backend window.
echo  ============================================================
echo.
timeout /t 15 /nobreak > nul
exit
