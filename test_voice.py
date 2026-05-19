import asyncio
import edge_tts
import os
import tempfile
import ctypes

async def generate():
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    comm = edge_tts.Communicate(
        "Good evening, sir. JARVIS is online and ready. How was your day?",
        voice="en-GB-RyanNeural",
        rate="+8%",
        pitch="-8Hz",
    )
    await comm.save(tmp.name)
    print(f"Generated: {tmp.name}  ({os.path.getsize(tmp.name)} bytes)")
    return tmp.name

path = asyncio.run(generate())

# Play via Windows MCI
winmm = ctypes.windll.winmm
safe_path = os.path.abspath(path)
winmm.mciSendStringW(f'open "{safe_path}" alias jarvis_test', None, 0, None)
print("Playing JARVIS voice — listen to your headset...")
winmm.mciSendStringW("play jarvis_test wait", None, 0, None)
winmm.mciSendStringW("close jarvis_test", None, 0, None)
print("Done. Did you hear it?")
