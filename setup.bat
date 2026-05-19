@echo off
title JARVIS Setup
color 0B
setlocal enabledelayedexpansion

echo.
echo  ============================================================
echo   JARVIS Setup Wizard
echo  ============================================================
echo.

REM ─── Check Python ───────────────────────────────────────────────────────────
echo  [1/9] Checking Python version...
python --version 2>&1 | find "Python 3" > nul
if %errorlevel% neq 0 (
    echo  [ERROR] Python 3 not found. Install Python 3.11+ from python.org
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a & set PYMIN=%%b
)
if !PYMAJ! LSS 3 (
    echo  [ERROR] Python 3.11+ required. Found: !PYVER!
    pause & exit /b 1
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 11 (
    echo  [ERROR] Python 3.11+ required. Found: !PYVER!
    pause & exit /b 1
)
echo  [OK]  Python !PYVER! found.

REM ─── Check Node.js ──────────────────────────────────────────────────────────
echo  [2/9] Checking Node.js version...
node --version 2>&1 | find "v" > nul
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js not found. Install Node.js 18+ from nodejs.org
    pause & exit /b 1
)
for /f "tokens=1 delims=v." %%v in ('node --version 2^>^&1') do set NODEVER=%%v
echo  [OK]  Node.js found.

REM ─── Create directories ─────────────────────────────────────────────────────
echo  [3/9] Creating directories...
if not exist "logs" mkdir logs
if not exist "models\piper" mkdir models\piper
echo  [OK]  Directories ready.

REM ─── Python dependencies ────────────────────────────────────────────────────
echo  [4/9] Installing Python dependencies (this may take several minutes)...
cd backend
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install Python dependencies.
    cd ..
    pause & exit /b 1
)
cd ..
echo  [OK]  Python dependencies installed.

REM ─── Download Whisper model ─────────────────────────────────────────────────
echo  [5/9] Downloading Whisper model (medium.en ~1.5GB)...
python -c "import whisper; whisper.load_model('medium.en'); print('Whisper model ready')"
if %errorlevel% neq 0 (
    echo  [WARN] Whisper model download failed. Voice input will be limited.
    echo         You can retry: python -c "import whisper; whisper.load_model('medium.en')"
) else (
    echo  [OK]  Whisper model downloaded.
)

REM ─── Download Piper TTS ─────────────────────────────────────────────────────
echo  [6/9] Setting up Piper TTS...
echo.
echo   Piper TTS requires manual setup:
echo   1. Download from: https://github.com/rhasspy/piper/releases
echo   2. Extract piper.exe to: models\piper\
echo   3. Download voice: en_US-lessac-medium.onnx
echo      from: https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium
echo   4. Place .onnx and .onnx.json in: models\piper\
echo.
echo   NOTE: Without Piper, JARVIS will use Windows built-in TTS (lower quality)
echo.

REM ─── Node dependencies ──────────────────────────────────────────────────────
echo  [7/9] Installing Node.js dependencies...
cd frontend
npm install --silent
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to install Node.js dependencies.
    cd ..
    pause & exit /b 1
)
cd ..
echo  [OK]  Node.js dependencies installed.

REM ─── Configure API key ──────────────────────────────────────────────────────
echo  [8/9] Configuring API key...
if not exist ".env" (
    copy ".env.example" ".env" > nul
    echo.
    set /p APIKEY= "  Enter your Anthropic API key (from console.anthropic.com): "
    REM Write key to .env using PowerShell to avoid escaping issues
    powershell -NoProfile -Command "(Get-Content '.env') -replace 'your_api_key_here', '!APIKEY!' | Set-Content '.env'"
    echo  [OK]  .env file created.
) else (
    echo  [OK]  .env file already exists.
)

REM ─── Test backend ───────────────────────────────────────────────────────────
echo  [9/9] Testing backend startup...
cd backend
start /B python main.py > ..\logs\test.log 2>&1
timeout /t 5 /nobreak > nul
curl -s http://localhost:8000/api/health > nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK]  Backend test passed.
) else (
    echo  [WARN] Backend test inconclusive. Check logs\test.log if issues arise.
)
taskkill /F /IM python.exe /T > nul 2>&1
cd ..

echo.
echo  ============================================================
echo   Setup Complete!
echo.
echo   Next steps:
echo   1. Ensure .env has your ANTHROPIC_API_KEY
echo   2. (Optional) Set up Piper TTS as described above
echo   3. Run start.bat to launch JARVIS
echo.
echo   Press Ctrl+Shift+Space after launch to activate voice input
echo  ============================================================
echo.
pause
