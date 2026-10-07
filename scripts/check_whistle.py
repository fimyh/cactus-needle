from pathlib import Path
from time import perf_counter
import wave

import needle

ROOT = Path(__file__).resolve().parents[1]
AUDIO_PATH = ROOT / "data" / "test_clip.wav"


def main() -> None:
    if not AUDIO_PATH.is_file():
        raise FileNotFoundError(
            f"Add your test recording here: {AUDIO_PATH}"
        )

    with wave.open(str(AUDIO_PATH), "rb") as audio:
        sample_rate = audio.getframerate()
        channels = audio.getnchannels()
        duration = audio.getnframes() / sample_rate

    if sample_rate != 16000 or channels != 1:
        raise ValueError("Use a 16 kHz mono WAV recording.")

    if not 0 < duration <= 30:
        raise ValueError("Recording must be between 0 and 30 seconds.")

    started = perf_counter()
    result = needle.transcribe(str(AUDIO_PATH))
    elapsed = perf_counter() - started

    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Transcription time: {elapsed:.2f} seconds")
    print("Transcript:", result.get("text", ""))
    print("Returned fields:", sorted(result))


if __name__ == "__main__":
    main()