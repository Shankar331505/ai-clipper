"""
Transcribe an audio/video file using Groq's Whisper API.
Usage: python transcribe.py <input_video> <output_json>
"""
import sys
import os
import json
import requests

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def transcribe(input_path: str, output_path: str):
    with open(input_path, "rb") as f:
        files = {"file": f}
        data = {
            "model": "whisper-large-v3-turbo",
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
        }
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        print(f"Uploading {input_path} to Groq Whisper...")
        resp = requests.post(GROQ_URL, headers=headers, files=files, data=data, timeout=600)
        resp.raise_for_status()

    result = resp.json()

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
