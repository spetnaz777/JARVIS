# JARVIS — Just A Rather Very Intelligent System

A JARVIS-style AI assistant for Windows with voice control, system management, and an Iron Man HUD aesthetic.

```
  ╔══════════════════════════════════════╗
  ║  J.A.R.V.I.S  v1.0  ● ONLINE        ║
  ║  ┌──────────────────────────────┐    ║
  ║  │    ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌   │    ║
  ║  │  ◌     [arc reactor viz]  ◌  │    ║
  ║  │    ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌ ◌   │    ║
  ║  └──────────────────────────────┘    ║
  ║  > How can I assist you?             ║
  ╚══════════════════════════════════════╝
```

---

## Features

- **Voice Conversation** — Whisper STT + Piper TTS for fully offline voice I/O
- **Claude Integration** — Powered by Claude Sonnet via Anthropic API
- **Command Execution** — Run PowerShell/CMD commands with a safety system
- **File Search** — Fast indexed search across your filesystem
- **System Monitoring** — Real-time CPU, memory, disk stats
- **Iron Man HUD** — Glassmorphism UI with arc reactor visualizer
- **Always-on-top** — Floating overlay, transparent, draggable

---

## Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| RAM | 8 GB | 16 GB |
| Disk | 5 GB | 10 GB |
| OS | Windows 10 | Windows 11 |
| Anthropic API key | Required | — |

---

## Installation

### Automated (Recommended)

```batch
# 1. Clone or download the project
cd C:\Users\YourName
# (place JARVIS folder here)

# 2. Run the setup wizard
setup.bat
```

The wizard will:
1. Verify Python 3.11+ and Node.js 18+
2. Install all Python dependencies
3. Download the Whisper `medium.en` model (~1.5 GB)
4. Install Node.js dependencies
5. Prompt for your Anthropic API key
6. Run a backend connectivity test

### Manual Installation

**Step 1 — Python dependencies**
```batch
cd JARVIS\backend
pip install -r requirements.txt
```

**Step 2 — Whisper model** (auto-downloads on first use, or pre-download)
```python
python -c "import whisper; whisper.load_model('medium.en')"
```

**Step 3 — Piper TTS** (optional — Windows TTS used as fallback)
1. Download `piper_windows_amd64.zip` from [Piper Releases](https://github.com/rhasspy/piper/releases)
2. Extract `piper.exe` to `JARVIS\models\piper\`
3. Download `en_US-lessac-medium.onnx` and `en_US-lessac-medium.onnx.json` from [Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium)
4. Place both files in `JARVIS\models\piper\`

**Step 4 — Node.js dependencies**
```batch
cd JARVIS\frontend
npm install
```

**Step 5 — Configure environment**
```batch
cd JARVIS
copy .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

---

## Configuration

Edit `JARVIS\.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...       # Required
WHISPER_MODEL=medium.en             # tiny.en / base.en / small.en / medium.en / large
PIPER_VOICE=en_US-lessac-medium    # Voice model name
BACKEND_PORT=8000                   # API server port
LOG_LEVEL=INFO                      # DEBUG / INFO / WARNING / ERROR
```

---

## Usage

### Launch

```batch
JARVIS\start.bat
```

Or manually:
```batch
# Terminal 1 — Backend
cd JARVIS\backend
python main.py

# Terminal 2 — Frontend
cd JARVIS\frontend
npm start
```

### Controls

| Action | Method |
|---|---|
| Activate voice input | `Ctrl+Shift+Space` |
| Stop voice recording | `Ctrl+Shift+Space` again |
| Toggle window visibility | `Ctrl+Shift+H` |
| Send text message | Type in input box + `Enter` |
| Minimize to corner | Click `−` button |
| Restore from minimized | Click the arc reactor |
| Clear conversation | "Clear history" link |

### Voice Commands (Examples)

```
"What's running on my computer?"
"Search for any PDF files in my documents"
"What's my CPU usage right now?"
"Open a new PowerShell window"
"How much free disk space do I have?"
"List the files in my Downloads folder"
```

---

## Safety System

JARVIS classifies every command before execution:

| Risk Level | Color | Behavior | Examples |
|---|---|---|---|
| STANDARD | Blue | Auto-execute | `dir`, `echo`, `Get-Process` |
| ELEVATED | Yellow | Requires confirmation | `pip install`, `taskkill`, `schtasks` |
| CRITICAL | Red | Requires confirmation, 10s timeout | `rm -rf`, `shutdown`, registry edits |

**Confirmation dialog features:**
- Full command preview
- Risk explanation
- Allow (`Enter`) / Deny (`Esc`) buttons
- 10-second countdown — defaults to **Deny**
- "Remember for session" checkbox

**Blocked by default:**
- File deletion (`rm -rf`, `del /f`, `Remove-Item`)
- System shutdown/restart
- Registry modifications (any HKLM/HKCU writes)
- Firewall rule changes
- Critical process termination (`csrss.exe`, `lsass.exe`, etc.)
- Software installations
- Service modifications

---

## Architecture

```
JARVIS/
├── backend/                    Python 3.11 / FastAPI
│   ├── main.py                 REST API + WebSocket server (port 8000)
│   ├── claude_brain.py         Anthropic SDK, conversation history
│   ├── voice_handler.py        Whisper STT, Piper/Windows TTS
│   ├── command_executor.py     PowerShell execution, timeout handling
│   ├── safety_checker.py       Risk classification, pattern matching
│   ├── file_manager.py         Indexed file search, glob patterns
│   ├── system_controller.py    psutil metrics, process listing
│   └── config.py               Environment config
│
└── frontend/                   Electron 31 + React 18
    ├── electron-main.js         Window management, global hotkeys
    └── src/
        ├── components/
        │   ├── HUD.jsx          Main overlay, state management
        │   ├── Visualizer.jsx   Canvas arc reactor animation
        │   ├── ConfirmDialog.jsx Safety confirmation modal
        │   ├── TranscriptDisplay.jsx  Conversation history
        │   └── StatusIndicator.jsx    State badge
        └── utils/api.js         Axios API client
```

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Backend status check |
| POST | `/api/chat` | Text chat with Claude |
| GET | `/api/chat/history` | Conversation history |
| DELETE | `/api/chat/history` | Clear history |
| POST | `/api/voice/start` | Begin audio recording |
| POST | `/api/voice/stop` | Stop, transcribe, respond |
| POST | `/api/voice/speak` | TTS for given text |
| GET | `/api/voice/status` | Recording/playing state + visualizer data |
| POST | `/api/command/execute` | Execute system command |
| POST | `/api/command/check` | Check command risk level |
| GET | `/api/files/search` | Fuzzy file search |
| GET | `/api/files/glob` | Glob pattern search |
| GET | `/api/files/info` | File metadata |
| GET | `/api/system/status` | CPU/memory/disk stats |
| GET | `/api/system/processes` | Top processes by CPU |
| WS | `/ws` | Real-time bidirectional communication |

---

## Troubleshooting

**"Backend offline" shown in UI**
- Ensure `python main.py` is running in `backend/`
- Check `logs/backend.log` for errors
- Verify port 8000 is free: `netstat -ano | findstr :8000`

**"Authentication failed" error**
- Your `ANTHROPIC_API_KEY` in `.env` is missing or invalid
- Get a key at https://console.anthropic.com

**Voice input not working**
- Confirm your microphone is set as the default input device
- Try a smaller Whisper model: set `WHISPER_MODEL=base.en` in `.env`
- Check `logs/backend.log` for audio device errors

**No speech output**
- If Piper is not installed, Windows TTS is used automatically
- Verify audio output device is working
- Check `logs/backend.log` for TTS errors

**Window is fully transparent / invisible**
- Ensure your Windows display settings have hardware acceleration enabled
- Try disabling Electron transparency: in `electron-main.js` set `transparent: false`

**"Module not found" errors**
- Re-run `pip install -r requirements.txt` in the `backend/` directory
- For Node errors, delete `frontend/node_modules/` and re-run `npm install`

**Whisper download is very slow**
- Models are cached in `%USERPROFILE%\.cache\whisper\` after first download
- Use `tiny.en` for faster startup (lower accuracy): `WHISPER_MODEL=tiny.en`

---

## Known Limitations

1. **Whisper latency** — The `medium.en` model takes ~1-3 seconds for transcription on CPU. Use a GPU or switch to `small.en` for faster response.
2. **Piper TTS** — Requires manual download; Windows TTS fallback has lower voice quality.
3. **Volume control** — The set_volume function works via keyboard simulation; hardware-specific APIs would be more reliable.
4. **Screen brightness** — Not currently supported (requires hardware-specific drivers).
5. **Multi-monitor** — Window positioning uses primary display only.
6. **macOS/Linux** — Not tested; Windows-specific APIs are used throughout.

---

## Future Roadmap

- [ ] Screen capture + vision analysis ("What's on my screen?")
- [ ] Calendar/email integration
- [ ] Custom wake word (replace hotkey)
- [ ] Plugin system for custom commands
- [ ] GPU acceleration for Whisper
- [ ] Dark/light theme toggle
- [ ] Export conversation history
- [ ] Streaming Claude responses (typewriter effect)
- [ ] Multi-language support

---

## License

MIT — use freely, at your own risk. JARVIS is a personal productivity tool; do not use for unauthorized system access.
