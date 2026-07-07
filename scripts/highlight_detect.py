"""
Feed the transcript to Claude and get back candidate clip timestamps.
Usage: python highlight_detect.py <transcript_json> <clips_output_json>
"""
import sys
import os
import json
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You analyze podcast/video transcripts and identify segments \
that would work well as standalone short-form clips (for YouTube Shorts / \
Instagram Reels). Look for moments with a strong hook, emotional peak, \
surprising claim, or self-contained story/argument.

Respond ONLY with a JSON array, no other text, no markdown fences. Each item:
{
  "start_time": <seconds, float>,
  "end_time": <seconds, float>,
  "hook_score": <1-10 integer>,
  "reason": "<one sentence>"
}

Return 3 to 6 clips. Each clip should be 20-60 seconds long."""


def build_transcript_text(transcript: dict) -> str:
    segments = transcript.get("segments", [])
    lines = []
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text'].strip()}")
    return "\n".join(lines)


def detect_highlights(transcript_path: str, output_path: str):
    with open(transcript_path) as f:
        transcript = json.load(f)

    transcript_text = build_transcript_text(transcript)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-sonnet-5",
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Transcript:\n\n{transcript_text}"}
        ],
    }

    print("Calling Claude for highlight detection...")
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    text_blocks = [b["text"] for b in result["content"] if b["type"] == "text"]
    raw_text = "".join(text_blocks).strip()

    # Strip accidental markdown fences just in case
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1)

    clips = json.loads(raw_text)

    with open(output_path, "w") as out:
        json.dump(clips, out, indent=2)

    print(f"Found {len(clips)} candidate clips -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python highlight_detect.py <transcript_json> <clips_output_json>")
        sys.exit(1)
    detect_highlights(sys.argv[1], sys.argv[2])
