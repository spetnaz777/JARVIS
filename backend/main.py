import asyncio
import json
import logging
import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from config import config

# Configure loguru
os.makedirs("../logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=config.LOG_LEVEL)
logger.add(
    "../logs/jarvis.log",
    rotation="10 MB",
    retention=5,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{line} | {message}",
)

from claude_brain import claude_brain
from voice_handler import voice_handler
from command_executor import command_executor
from file_manager import file_manager
from system_controller import system_controller
from safety_checker import safety_checker, RiskLevel


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JARVIS backend starting up...")
    try:
        config.validate()
        logger.info("Configuration validated")
    except ValueError as e:
        logger.warning(f"Config warning: {e}")
    logger.info(f"Server running on port {config.BACKEND_PORT}")
    yield
    logger.info("JARVIS backend shutting down")


app = FastAPI(title="JARVIS Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    stream: bool = False


class CommandRequest(BaseModel):
    command: str
    confirmed: bool = False


class VoiceTextRequest(BaseModel):
    text: str


# ─── Chat Endpoints ──────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    try:
        response = await claude_brain.get_response(request.message)
        return {
            "response": response,
            "stats": claude_brain.get_stats(),
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history")
async def get_history():
    return {"history": claude_brain.get_history()}


@app.delete("/api/chat/history")
async def clear_history():
    claude_brain.clear_history()
    return {"status": "cleared"}


# ─── Voice Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/voice/start")
async def voice_start():
    if voice_handler.is_recording:
        return {"status": "already_recording"}
    success = voice_handler.start_recording()
    return {"status": "recording" if success else "failed"}


@app.post("/api/voice/stop")
async def voice_stop():
    audio_data = voice_handler.stop_recording()
    if audio_data is None:
        return {"status": "no_audio", "transcript": "", "response": ""}

    transcript = await voice_handler.transcribe(audio_data)
    if not transcript:
        return {"status": "no_transcript", "transcript": "", "response": ""}

    response = await claude_brain.get_response(transcript)

    asyncio.create_task(voice_handler.speak(response))

    return {
        "status": "success",
        "transcript": transcript,
        "response": response,
    }


@app.post("/api/voice/speak")
async def voice_speak(request: VoiceTextRequest):
    asyncio.create_task(voice_handler.speak(request.text))
    return {"status": "speaking"}


@app.get("/api/voice/status")
async def voice_status():
    return {
        "is_recording": voice_handler.is_recording,
        "is_playing": voice_handler.is_playing,
        "visualizer": voice_handler.get_visualizer_state(),
    }


# ─── Command Endpoints ────────────────────────────────────────────────────────

@app.post("/api/command/execute")
async def execute_command(request: CommandRequest):
    if not request.command.strip():
        raise HTTPException(status_code=400, detail="Empty command")

    result = await command_executor.execute(request.command, bypass_safety=request.confirmed)

    response_data = {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.return_code,
        "command": result.command,
        "blocked": result.blocked,
    }

    if result.safety_result:
        response_data["safety"] = {
            "risk_level": result.safety_result.risk_level.value,
            "reason": result.safety_result.reason,
            "requires_confirmation": result.safety_result.requires_confirmation,
        }

    return response_data


@app.post("/api/command/check")
async def check_command(request: CommandRequest):
    safety_result = safety_checker.check_command(request.command)
    return {
        "risk_level": safety_result.risk_level.value,
        "requires_confirmation": safety_result.requires_confirmation,
        "reason": safety_result.reason,
        "explanation": safety_checker.get_risk_explanation(safety_result),
    }


# ─── File Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/files/search")
async def search_files(
    query: str = Query(..., min_length=1),
    file_type: Optional[str] = Query(None),
    max_results: int = Query(20, ge=1, le=100),
):
    try:
        results = file_manager.search(query, max_results=max_results, file_type=file_type)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"File search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/glob")
async def glob_files(pattern: str = Query(...), directory: Optional[str] = Query(None)):
    try:
        results = file_manager.glob_search(pattern, directory)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files/info")
async def file_info(path: str = Query(...)):
    info = file_manager.get_file_info(path)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
    return info


# ─── System Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/system/status")
async def system_status():
    try:
        status = system_controller.get_status()
        return status.to_dict()
    except Exception as e:
        logger.error(f"System status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/processes")
async def system_processes(n: int = Query(10, ge=1, le=50)):
    return {"processes": system_controller.get_top_processes(n)}


@app.get("/api/system/network")
async def system_network():
    return system_controller.get_network_info()


# ─── WebSocket for Real-time Updates ─────────────────────────────────────────

connected_clients: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg.get("type") == "chat":
                text = msg.get("text", "")
                if text:
                    response = await claude_brain.get_response(text)
                    await websocket.send_json({"type": "chat_response", "text": response})

            elif msg.get("type") == "voice_start":
                voice_handler.start_recording()
                await websocket.send_json({"type": "recording_started"})

            elif msg.get("type") == "voice_stop":
                audio_data = voice_handler.stop_recording()
                if audio_data is not None:
                    transcript = await voice_handler.transcribe(audio_data)
                    if transcript:
                        response = await claude_brain.get_response(transcript)
                        asyncio.create_task(voice_handler.speak(response))
                        await websocket.send_json({
                            "type": "voice_response",
                            "transcript": transcript,
                            "response": response,
                        })

    except asyncio.TimeoutError:
        pass
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


async def broadcast(message: dict):
    dead = []
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            dead.append(client)
    for d in dead:
        connected_clients.remove(d)


@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "version": "1.0.0",
        "model": config.CLAUDE_MODEL,
        "api_key_set": bool(config.ANTHROPIC_API_KEY),
    }


# ─── Greeting Endpoint ────────────────────────────────────────────────────────

@app.get("/api/greet")
async def greet():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    hour = now.hour

    if 5 <= hour < 12:
        time_phrase = "Good morning"
        followup = "I hope you slept well. What shall we get done today?"
    elif 12 <= hour < 17:
        time_phrase = "Good afternoon"
        followup = "How has your day been so far?"
    elif 17 <= hour < 22:
        time_phrase = "Good evening"
        followup = "How was your day, sir?"
    else:
        time_phrase = "Good evening"
        followup = "Burning the midnight oil, are we? How can I help?"

    greeting = f"{time_phrase}, sir. {followup}"
    return {
        "greeting": greeting,
        "time_phrase": time_phrase,
        "hour": hour,
        "timezone": config.TIMEZONE,
    }


# ─── Audio Device List ────────────────────────────────────────────────────────

@app.get("/api/audio/devices")
async def list_audio_devices():
    import sounddevice as sd
    devices = sd.query_devices()
    inputs = [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices) if d["max_input_channels"] > 0
    ]
    outputs = [
        {"index": i, "name": d["name"], "channels": d["max_output_channels"]}
        for i, d in enumerate(devices) if d["max_output_channels"] > 0
    ]
    return {
        "inputs": inputs,
        "outputs": outputs,
        "current_input": config.AUDIO_INPUT_DEVICE,
        "current_output": config.AUDIO_OUTPUT_DEVICE,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=config.BACKEND_PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )
