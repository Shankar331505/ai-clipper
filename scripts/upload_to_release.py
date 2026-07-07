"""
Upload finished clips to a GitHub Release so they have a public URL Buffer
can use, then write that URL into each entry of metadata.json as "video_url".

Uses the `gh` CLI, which is preinstalled on GitHub-hosted Actions runners
and already authenticated via the GITHUB_TOKEN env var that Actions sets
automatically - no extra secret needed for this step.

Usage: python upload_to_release.py <metadata_json>
"""
import sys
import os
import json
import subprocess
import time

GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]  # e.g. "shankar/ai-clipper"
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))


def create_release(tag: str):
    cmd = [
        "gh", "release", "create", tag,
        "--title", f"Clips {tag}",
        "--notes", "Auto-generated clips from the AI clipping pipeline.",
    ]
    print(f"Creating release {tag}...")
    subprocess.run(cmd, check=True)


def upload_asset(tag: str, file_path: str):
    cmd = ["gh", "release", "upload", tag, file_path, "--clobber"]
    print(f"Uploading {file_path} to release {tag}...")
    subprocess.run(cmd, check=True)


def public_download_url(tag: str, filename: str) -> str:
    return f"https://github.com/{GITHUB_REPOSITORY}/releases/download/{tag}/{filename}"


def main(metadata_path: str):
    with open(metadata_path) as f:
        metadata = json.load(f)

    tag = f"clips-{GITHUB_RUN_ID}"
    create_release(tag)

    for meta in metadata:
        final_path = meta.get("final_path")
        if not final_path or not os.path.exists(final_path):
            print(f"Skipping {meta['clip_id']}: no final video file found at {final_path}")
            continue

        filename = os.path.basename(final_path)
        upload_asset(tag, final_path)
        meta["video_url"] = public_download_url(tag, filename)
        print(f"  {meta['clip_id']} -> {meta['video_url']}")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Updated {metadata_path} with public video URLs.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python upload_to_release.py <metadata_json>")
        sys.exit(1)
    main(sys.argv[1])
