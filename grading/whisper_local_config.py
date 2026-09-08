from pathlib import Path

WHISPER_CLI = Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = Path.home() / "whisper.cpp" / "models" / "ggml-base.en-q5_1.bin"
WHISPER_LANGUAGE = "en"
WHISPER_THREADS = 1
