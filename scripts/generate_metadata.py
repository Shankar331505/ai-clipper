"""
Generate a title, hook text, and hashtags for each clip using Claude.
Usage: python generate_metadata.py <clips.json> <metadata.json>
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
  "title": "<catchy title, max 60 chars>",
  "hook_text": "<EXACTLY 5-6 words. Must be a COMPLETE thought. This is the attention-grabbing context line shown above the video. Examples: 'KSI shocked by sparkling water tap', 'Drake caught texting during interview', 'Logan Paul loses bet on stream', 'Ronaldo refuses to shake hands'. NEVER exceed 6 words. NEVER leave it incomplete or cut off mid-sentence.>",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}

CRITICAL RULES FOR hook_text:
- MUST be exactly 5 or 6 words, no more, no less
- MUST be a complete meaningful sentence/phrase
- MUST describe the key moment in the clip
- Write in 3rd person present tense
- Do NOT end mid-thought (BAD: "KSI shocked by seeing by")
- Do NOT use filler words to pad length"""

def generate_metadata(clips_path: str, output_path: str):
    with open(clips_path) as f:
        clips = json.load(f)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    results = []
    for i, clip in enumerate(clips):
        clip_id = clip.get("clip_id") or f"{i+1:03d}"
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

        # HARD CAP: enforce 6 word max on hook_text
        hook_words = meta.get("hook_text", "").split()
        if len(hook_words) > 6:
            meta["hook_text"] = " ".join(hook_words[:6])
            print(f"  WARNING: hook_text truncated to 6 words: {meta['hook_text']}")

        meta["clip_id"] = clip_id
        meta["final_path"] = clip.get("final_path")
        results.append(meta)
        print(f"Generated metadata for {clip_id}: {meta['title']}")
        print(f"  Hook text ({len(meta['hook_text'].split())} words): {meta['hook_text']}")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_metadata.py <clips.json> <metadata.json>")
        sys.exit(1)
    generate_metadata(sys.argv[1], sys.argv[2])
