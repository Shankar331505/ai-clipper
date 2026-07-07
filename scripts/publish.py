"""
Publish finished clips to Buffer for scheduling to YouTube Shorts / Instagram Reels.

NOTE: Buffer's API has changed over the years (classic API vs newer GraphQL API).
Double check the current endpoint/auth format in Buffer's developer docs before
relying on this - this script assumes the classic REST-style "create update"
endpoint as a starting point and will likely need small adjustments.

Usage: python publish.py <metadata_json>
"""
import sys
import os
import json
import requests

BUFFER_ACCESS_TOKEN = os.environ["BUFFER_ACCESS_TOKEN"]
BUFFER_API_BASE = "https://api.bufferapp.com/1"


def get_profile_ids() -> list:
    resp = requests.get(
        f"{BUFFER_API_BASE}/profiles.json",
        params={"access_token": BUFFER_ACCESS_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    profiles = resp.json()
    return [p["id"] for p in profiles]


def publish_clip(meta: dict, profile_ids: list):
    caption = f"{meta['title']}\n\n{' '.join(meta['hashtags'])}"

    data = {
        "text": caption,
        "access_token": BUFFER_ACCESS_TOKEN,
    }
    for pid in profile_ids:
        data[f"profile_ids[]"] = pid

    # NOTE: media upload via Buffer's API requires the media be hosted at a
    # public URL, or uploaded through their media endpoint first - you'll
    # need to upload final_path to some storage (e.g. a GitHub release asset,
    # or S3/Cloudflare R2) and pass that URL here as media[video][url].
    print(f"Would publish clip {meta['clip_id']}: {meta['title']}")
    print("NOTE: wire up media hosting before this actually posts video content.")

    # Example of the eventual call once media hosting is in place:
    # resp = requests.post(f"{BUFFER_API_BASE}/updates/create.json", data=data, timeout=60)
    # resp.raise_for_status()
    # print(resp.json())


def main(metadata_path: str):
    with open(metadata_path) as f:
        metadata = json.load(f)

    profile_ids = get_profile_ids()
    print(f"Found {len(profile_ids)} connected Buffer profiles")

    for meta in metadata:
        publish_clip(meta, profile_ids)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python publish.py <metadata_json>")
        sys.exit(1)
    main(sys.argv[1])
