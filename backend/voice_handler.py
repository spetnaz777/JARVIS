import asyncio
import io
import os
import queue
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Callable

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


class VoiceHandler:
    def __init__(self):
        self.whisper_model = None
        self.is_recording = False
        self.is_playing = False
        self.audio_queue: queue.Queue = queue.Queue()
        self.visualizer = AudioVisualizer()
        self.recording_thread: Optional[threading.Thread] = None
        self.playback_queue: queue.Queue = queue.Queue()
        self.playback_thread: Optional[threading.Thread] = None
        self._start_playback_worker()

    def _start_playback_worker(self):
        def worker():
            while True:
                audio_path = self.playback_queue.get()
                if audio_path is None:
                    break
                try:
                    self._play_audio_file(audio_path)
                except Exception as e:
                    logger.error(f"Playback error: {e}")
                finally:
                    self.playback_queue.task_done()
                    if os.path.exists(audio_path) and "tmp" in audio_path:
                        try:
                            os.unlink(audio_path)
                        except Exception:
                            pass

        self.playback_thread = threading.Thread(target=worker, daemon=True)
        self.playback_thread.start()

    def load_whisper_model(self):
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
        if not hasattr(self, "audio_frames") or not self.audio_frames:
            return None
        audio_data = np.concatenate(self.audio_frames, axis=0)
        logger.info(f"Recording stopped. Duration: {len(audio_data) / config.SAMPLE_RATE:.2f}s")
        return audio_data

    def _record_audio(self):
        frames = []
        silence_frames = 0
        silence_threshold_frames = int(config.SILENCE_DURATION * config.SAMPLE_RATE / config.CHUNK_SIZE)

        def callback(indata, frame_count, time_info, status):
            if status:
                logger.warning(f"Audio input status: {status}")
            frames.append(indata.copy())
            self.visualizer.update(indata[:, 0] if indata.ndim > 1 else indata)

        try:
            with sd.InputStream(
                samplerate=config.SAMPLE_RATE,
                channels=config.CHANNELS,
                dtype=np.int16,
                blocksize=config.CHUNK_SIZE,
                callback=callback,
            ):
                while self.is_recording:
                    time.sleep(0.01)

                    if frames:
                        recent = frames[-1].flatten().astype(np.float32)
                        rms = np.sqrt(np.mean(recent ** 2))
                        if rms < config.SILENCE_THRESHOLD * 32768:
                            silence_frames += 1
                        else:
                            silence_frames = 0

                        if silence_frames >= silence_threshold_frames:
                            logger.info("Silence detected — auto-stopping recording")
                            self.is_recording = False
                            break

        except Exception as e:
            logger.error(f"Recording error: {e}")
        finally:
            self.audio_frames = frames

    async def transcribe(self, audio_data: np.ndarray) -> str:
        if self.whisper_model is None:
            if not self.load_whisper_model():
                return ""

        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, self._transcribe_sync, audio_data)
            return text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def _transcribe_sync(self, audio_data: np.ndarray) -> str:
        audio_float = audio_data.astype(np.float32) / 32768.0
        if audio_float.ndim > 1:
            audio_float = audio_float.mean(axis=1)

        result = self.whisper_model.transcribe(audio_float, language="en", fp16=False)
        text = result["text"].strip()
        logger.info(f"Transcription: {text}")
        return text

    async def speak(self, text: str) -> bool:
        try:
            audio_path = await asyncio.get_event_loop().run_in_executor(
                None, self._synthesize_speech, text
            )
            if audio_path:
                self.playback_queue.put(audio_path)
                return True
            return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False

    def _synthesize_speech(self, text: str) -> Optional[str]:
        piper_exe = config.PIPER_DIR / "piper.exe"
        voice_model = config.PIPER_DIR / f"{config.PIPER_VOICE}.onnx"

        if not piper_exe.exists():
            logger.warning("Piper TTS not found — using system TTS fallback")
            return self._windows_tts_fallback(text)

        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp_file.name
            tmp_file.close()

            proc = subprocess.run(
                [str(piper_exe), "--model", str(voice_model), "--output_file", tmp_path],
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode == 0 and os.path.exists(tmp_path):
                return tmp_path
            else:
                logger.error(f"Piper TTS failed: {proc.stderr}")
                return self._windows_tts_fallback(text)

        except Exception as e:
            logger.error(f"Piper TTS error: {e}")
            return self._windows_tts_fallback(text)

    def _windows_tts_fallback(self, text: str) -> Optional[str]:
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp_file.name
            tmp_file.close()

            ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{tmp_path}')
$synth.Speak('{text.replace("'", "")}')
$synth.Dispose()
"""
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                timeout=30,
            )
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                return tmp_path
        except Exception as e:
            logger.error(f"Windows TTS fallback error: {e}")
        return None

    def _play_audio_file(self, audio_path: str):
        try:
            data, samplerate = sf.read(audio_path)
            self.is_playing = True
            sd.play(data, samplerate)
            sd.wait()
            self.is_playing = False
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            self.is_playing = False

    def get_visualizer_state(self) -> dict:
        return self.visualizer.get_state()


voice_handler = VoiceHandler()
