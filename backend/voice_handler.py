import asyncio
import ctypes
import os
import queue
import tempfile
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from loguru import logger

from config import config

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Whisper not available — STT disabled")


# ─── Windows MCI audio playback (built-in, handles mp3/wav) ─────────────────

def _mci_play(path: str) -> None:
    """Play audio via Windows MCI — no external dependencies, handles mp3."""
    winmm = ctypes.windll.winmm
    path = os.path.abspath(path).replace("/", "\\")
    alias = "jarvis_snd"
    winmm.mciSendStringW(f'open "{path}" alias {alias}', None, 0, None)
    err = winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
    winmm.mciSendStringW(f"close {alias}", None, 0, None)
    if err:
        logger.warning(f"MCI playback error code: {err}")


# ─── Audio Visualizer ────────────────────────────────────────────────────────

class AudioVisualizer:
    def __init__(self):
        self.current_level: float = 0.0
        self.bars: list[float] = [0.0] * 12
        self._lock = threading.Lock()

    def update(self, audio_chunk: np.ndarray):
        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))
        normalized = min(rms / 3000.0, 1.0)
        with self._lock:
            self.current_level = normalized
            self.bars = [
                max(0.0, normalized * (0.6 + 0.4 * abs(np.sin(i * 1.3 + time.time() * 3))))
                for i in range(12)
            ]

    def get_state(self) -> dict:
        with self._lock:
            return {"level": self.current_level, "bars": self.bars.copy()}


# ─── Main VoiceHandler ───────────────────────────────────────────────────────

class VoiceHandler:
    def __init__(self):
        self.whisper_model = None
        self.is_recording = False
        self.is_playing = False
        self.visualizer = AudioVisualizer()
        self.recording_thread: Optional[threading.Thread] = None
        self.audio_frames: list = []
        self.playback_queue: queue.Queue = queue.Queue()
        self._start_playback_worker()
        self._log_audio_devices()

    # ── Device Discovery ─────────────────────────────────────────────────────

    def _log_audio_devices(self):
        """Log available audio devices so the user can pick one."""
        devices = sd.query_devices()
        logger.info("Available audio input devices:")
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                marker = " ◀ SELECTED" if i == config.AUDIO_INPUT_DEVICE else ""
                logger.info(f"  [{i}] {d['name']}{marker}")
        if config.AUDIO_INPUT_DEVICE is None:
            logger.info("  Using system default input device")

    # ── Playback Worker ───────────────────────────────────────────────────────

    def _start_playback_worker(self):
        def worker():
            while True:
                audio_path = self.playback_queue.get()
                if audio_path is None:
                    break
                try:
                    self.is_playing = True
                    _mci_play(audio_path)
                    self.is_playing = False
                except Exception as e:
                    logger.error(f"Playback error: {e}")
                    self.is_playing = False
                finally:
                    self.playback_queue.task_done()
                    try:
                        if os.path.exists(audio_path):
                            os.unlink(audio_path)
                    except Exception:
                        pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ── Whisper Model ─────────────────────────────────────────────────────────

    def load_whisper_model(self) -> bool:
        if not WHISPER_AVAILABLE:
            logger.error("Whisper package not installed")
            return False
        try:
            logger.info(f"Loading Whisper model: {config.WHISPER_MODEL}")
            self.whisper_model = whisper.load_model(config.WHISPER_MODEL)
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    # ── Recording ─────────────────────────────────────────────────────────────

    def start_recording(self) -> bool:
        if self.is_recording:
            return False
        self.is_recording = True
        self.audio_frames = []
        self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
        self.recording_thread.start()
        logger.info("Recording started")
        return True

    def stop_recording(self) -> Optional[np.ndarray]:
        if not self.is_recording:
            return None
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=3.0)
        if not self.audio_frames:
            return None
        audio_data = np.concatenate(self.audio_frames, axis=0)
        logger.info(f"Recording stopped — {len(audio_data)/config.SAMPLE_RATE:.2f}s captured")
        return audio_data

    def _record_audio(self):
        silence_threshold = config.SILENCE_THRESHOLD * 32768
        silence_needed = int(config.SILENCE_DURATION * config.SAMPLE_RATE / config.CHUNK_SIZE)
        silence_count = 0
        frames = []

        def callback(indata, frame_count, time_info, status):
            if status:
                logger.debug(f"Audio status: {status}")
            frames.append(indata.copy())
            chunk = indata[:, 0] if indata.ndim > 1 else indata
            self.visualizer.update(chunk)

        try:
            with sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=config.CHANNELS,
                dtype=np.int16,
                blocksize=config.CHUNK_SIZE,
                callback=callback,
                device=config.AUDIO_INPUT_DEVICE,
            ):
                while self.is_recording:
                    time.sleep(0.01)
                    if frames:
                        rms = np.sqrt(np.mean(frames[-1].astype(np.float32) ** 2))
                        if rms < silence_threshold:
                            silence_count += 1
                        else:
                            silence_count = 0
                        if silence_count >= silence_needed:
                            logger.info("Silence detected — auto-stopping")
                            self.is_recording = False
        except Exception as e:
            logger.error(f"Recording error: {e}")
        finally:
            self.audio_frames = frames

    # ── Transcription ─────────────────────────────────────────────────────────

    async def transcribe(self, audio_data: np.ndarray) -> str:
        if self.whisper_model is None:
            if not self.load_whisper_model():
                return ""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._transcribe_sync, audio_data)
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def _transcribe_sync(self, audio_data: np.ndarray) -> str:
        audio = audio_data.astype(np.float32) / 32768.0
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        result = self.whisper_model.transcribe(audio, language="en", fp16=False)
        text = result["text"].strip()
        logger.info(f"Transcription: {text}")
        return text

    # ── TTS ───────────────────────────────────────────────────────────────────

    async def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        try:
            audio_path = await self._synthesize(text)
            if audio_path:
                self.playback_queue.put(audio_path)
                return True
        except Exception as e:
            logger.error(f"TTS error: {e}")
        return False

    async def _synthesize(self, text: str) -> Optional[str]:
        """Try edge-tts first (JARVIS voice), fall back to Windows SAPI."""
        # Strip markdown / command prefixes before speaking
        clean = text.replace("**", "").replace("*", "").replace("`", "")
        for prefix in ["CMD:", "FILE_SEARCH:"]:
            if prefix in clean:
                clean = clean.split(prefix)[0].strip()
        clean = clean[:600]  # cap length for voice output

        path = await self._edge_tts(clean)
        if path:
            return path
        return await asyncio.get_event_loop().run_in_executor(None, self._windows_tts, clean)

    async def _edge_tts(self, text: str) -> Optional[str]:
        """High-quality JARVIS voice using Microsoft Edge neural TTS."""
        try:
            import edge_tts
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()

            communicate = edge_tts.Communicate(
                text,
                voice="en-GB-RyanNeural",   # British male — closest to JARVIS
                rate="+8%",                  # slightly faster, more efficient
                pitch="-8Hz",                # slightly deeper, more authoritative
                volume="+0%",
            )
            await communicate.save(tmp.name)

            if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 1000:
                logger.info(f"Edge-TTS OK ({len(text)} chars)")
                return tmp.name
            os.unlink(tmp.name)
        except Exception as e:
            logger.warning(f"Edge-TTS unavailable: {e}")
        return None

    def _windows_tts(self, text: str) -> Optional[str]:
        """Fallback: Windows SAPI TTS → WAV → MCI playback."""
        import subprocess
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            safe = text.replace("'", "").replace('"', "")
            script = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 1; "
                f"$s.SetOutputToWaveFile('{tmp.name}'); "
                f"$s.Speak('{safe}'); "
                f"$s.Dispose()"
            )
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True, timeout=30,
            )
            if os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
                return tmp.name
        except Exception as e:
            logger.error(f"Windows TTS fallback error: {e}")
        return None

    # ── Status ────────────────────────────────────────────────────────────────

    def get_visualizer_state(self) -> dict:
        return self.visualizer.get_state()


voice_handler = VoiceHandler()
