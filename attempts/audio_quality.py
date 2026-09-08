import math
import os
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path


def _dbfs(samples):
    if not samples:
        return -120.0

    squares = sum(float(sample) * float(sample) for sample in samples)
    rms = math.sqrt(squares / len(samples))

    if rms <= 0:
        return -120.0

    return 20.0 * math.log10(rms / 32768.0)


def _energy_activity(samples, sample_rate, frame_ms=30, threshold_db=-42.0):
    frame_samples = max(1, int(sample_rate * frame_ms / 1000))
    total = 0
    active = 0

    for start in range(0, len(samples), frame_samples):
        frame = samples[start:start + frame_samples]

        if len(frame) < frame_samples:
            break

        total += 1

        if _dbfs(frame) >= threshold_db:
            active += 1

    return (active / total) if total else 0.0


def _webrtc_speech_ratio(wav_path):
    try:
        import webrtcvad
    except Exception:
        return None

    vad = webrtcvad.Vad(2)

    with wave.open(str(wav_path), "rb") as wav:
        rate = wav.getframerate()
        width = wav.getsampwidth()
        channels = wav.getnchannels()

        if rate != 16000 or width != 2 or channels != 1:
            return None

        pcm = wav.readframes(wav.getnframes())

    frame_ms = 30
    frame_bytes = int(16000 * frame_ms / 1000) * 2
    total = 0
    speech = 0

    for start in range(0, len(pcm), frame_bytes):
        frame = pcm[start:start + frame_bytes]

        if len(frame) != frame_bytes:
            break

        total += 1

        try:
            if vad.is_speech(frame, 16000):
                speech += 1
        except Exception:
            pass

    return (speech / total) if total else 0.0


def analyze_audio_file(source_path):
    source_path = Path(source_path)

    if not source_path.exists() or source_path.stat().st_size <= 0:
        return {
            "ok": False,
            "reason": "missing_audio",
            "duration": 0.0,
            "rms_dbfs": -120.0,
            "speech_ratio": 0.0,
            "energy_activity_ratio": 0.0,
        }

    fd, temp_name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(temp_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        with wave.open(str(temp_path), "rb") as wav:
            rate = wav.getframerate()
            frames = wav.getnframes()
            raw = wav.readframes(frames)

        samples = array("h")
        samples.frombytes(raw)

        duration = frames / float(rate) if rate else 0.0
        rms_dbfs = _dbfs(samples)
        energy_ratio = _energy_activity(samples, rate)
        vad_ratio = _webrtc_speech_ratio(temp_path)
        speech_ratio = (
            vad_ratio
            if vad_ratio is not None
            else energy_ratio
        )

        reason = None

        if duration < 0.8:
            reason = "too_short"
        elif rms_dbfs < -48.0:
            reason = "too_quiet"
        elif speech_ratio < 0.08:
            reason = "no_speech"

        return {
            "ok": reason is None,
            "reason": reason,
            "duration": round(duration, 3),
            "rms_dbfs": round(rms_dbfs, 2),
            "speech_ratio": round(float(speech_ratio), 4),
            "energy_activity_ratio": round(float(energy_ratio), 4),
            "vad_used": vad_ratio is not None,
        }

    except Exception as exc:
        return {
            "ok": True,
            "reason": "analysis_failed",
            "error": str(exc),
            "duration": None,
            "rms_dbfs": None,
            "speech_ratio": None,
            "energy_activity_ratio": None,
        }

    finally:
        temp_path.unlink(missing_ok=True)


def analyze_response_audio(response):
    audio = getattr(response, "audio_response", None)

    if not audio:
        return {
            "ok": False,
            "reason": "missing_audio",
            "duration": 0.0,
            "rms_dbfs": -120.0,
            "speech_ratio": 0.0,
            "energy_activity_ratio": 0.0,
        }

    try:
        path = audio.path
    except Exception:
        return {
            "ok": True,
            "reason": "path_unavailable",
            "duration": None,
            "rms_dbfs": None,
            "speech_ratio": None,
            "energy_activity_ratio": None,
        }

    return analyze_audio_file(path)
