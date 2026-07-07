"""
Generate a title, hook text, and hashtags for each clip using Claude.
Usage: python generate_metadata.py <clips_json> <metadata_output_json>
"""
import sys
import os
import json
import requests

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You write short-form video metadata for YouTube Shorts / \
Instagram Reels. Given a clip's reason/context, respond ONLY with JSON, no \
markdown fences:
{
  "title": "<punchy title under 60 characters>",
  "hook_text": "<on-screen hook text overlay, under 8 words>",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}"""


def generate_metadata(clips_path: str, output_path: str):
    with open(clips_path) as f:
        clips = json.load(f)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    results = []
    for clip in clips:
        body = {
            "model": "claude-sonnet-5",
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": f"Clip context: {clip.get('reason', '')}"}
            ],
        }
        resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        text_blocks = [b["text"] for b in result["content"] if b["type"] == "text"]
        raw_text = "".join(text_blocks).strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json\n", "", 1)

        meta = json.loads(raw_text)
        meta["clip_id"] = clip["clip_id"]
        meta["final_path"] = clip.get("final_path")
        results.append(meta)
        print(f"Generated metadata for {clip['clip_id']}: {meta['title']}")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_metadata.py <clips_json> <metadata_output_json>")
        sys.exit(1)
    generate_metadata(sys.argv[1], sys.argv[2])
