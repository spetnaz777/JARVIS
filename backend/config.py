import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

class Config:
    # API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Voice Settings
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "medium.en")
    PIPER_VOICE: str = os.getenv("PIPER_VOICE", "en_US-lessac-medium")

    # Server Settings
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Audio Settings
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    CHUNK_SIZE: int = 1024
    SILENCE_THRESHOLD: float = 0.01
    SILENCE_DURATION: float = 2.0  # seconds before auto-stop

    # Audio Device Selection (None = use Windows default)
    # Run: python -c "import sounddevice as sd; print(sd.query_devices())" to list
    AUDIO_INPUT_DEVICE: int | None = (
        int(os.getenv("AUDIO_INPUT_DEVICE")) if os.getenv("AUDIO_INPUT_DEVICE", "").strip() else None
    )
    AUDIO_OUTPUT_DEVICE: int | None = (
        int(os.getenv("AUDIO_OUTPUT_DEVICE")) if os.getenv("AUDIO_OUTPUT_DEVICE", "").strip() else None
    )

    # Timezone for greetings
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Toronto")

    # Claude Settings
    CLAUDE_MODEL: str = "claude-sonnet-4-5"
    MAX_HISTORY: int = 10
    MAX_TOKENS: int = 1024

    # Command Settings
    COMMAND_TIMEOUT: int = 30

    # Paths
    LOGS_DIR: Path = BASE_DIR / "logs"
    MODELS_DIR: Path = BASE_DIR / "models"
    PIPER_DIR: Path = BASE_DIR / "models" / "piper"

    # File Search Settings
    SEARCH_DIRS: list = [
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Downloads"),
        os.path.expanduser("~"),
    ]

    @classmethod
    def validate(cls):
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set in .env file")
        cls.LOGS_DIR.mkdir(exist_ok=True)
        cls.MODELS_DIR.mkdir(exist_ok=True)
        cls.PIPER_DIR.mkdir(exist_ok=True)

config = Config()
