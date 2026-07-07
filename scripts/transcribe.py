"""
Transcribe an audio/video file using Groq's Whisper API.
Usage: python transcribe.py <input_video> <output_json>
"""
import sys
import os
import json
import requests
import subprocess
import tempfile

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe(input_path: str, output_path: str):
    # Extract and compress audio to a temporary MP3 file using ffmpeg to avoid 413 Payload Too Large
    audio_path = input_path
    temp_audio_path = None
    try:
        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_audio_path = temp_audio_file.name
        temp_audio_file.close()

        print(f"Extracting audio from {input_path} to {temp_audio_path}...")
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-vn",                 # No video
            "-acodec", "libmp3lame",
            "-ac", "1",            # Mono
            "-ar", "16000",        # 16kHz
            "-b:a", "64k",         # 64kbps bitrate
            temp_audio_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            audio_path = temp_audio_path
            print("Audio extraction successful.")
        else:
            print(f"Warning: ffmpeg failed (exit code {res.returncode}). Using original file. Error: {res.stderr}")
    except Exception as e:
        print(f"Warning: Failed to extract audio using ffmpeg ({e}). Using original file.")

    try:
        with open(audio_path, "rb") as f:
            files = {"file": f}
            data = {
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            }
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

            print(f"Uploading {audio_path} to Groq Whisper...")
            resp = requests.post(GROQ_URL, headers=headers, files=files, data=data, timeout=600)
            resp.raise_for_status()

        result = resp.json()
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception as e:
                print(f"Warning: Failed to clean up temp audio file ({e})")

    with open(output_path, "w") as out:
        json.dump(result, out, indent=2)

    print(f"Transcript saved to {output_path}")
    print(f"Duration: {result.get('duration', 'unknown')}s, "
          f"segments: {len(result.get('segments', []))}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python transcribe.py <input_video> <output_json>")
        sys.exit(1)
    transcribe(sys.argv[1], sys.argv[2])
