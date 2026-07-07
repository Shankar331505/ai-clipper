"""
Cut clips from the source video based on detected highlight timestamps.
Usage: python cut_clips.py <source_video> <clips_json> <transcript_json>
"""
import sys
import os
import json
import subprocess

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def cut_clips(source_video: str, clips_path: str, transcript_path: str):
    with open(clips_path) as f:
        clips = json.load(f)

    for i, clip in enumerate(clips):
        clip_id = f"{i+1:03d}"
        start = clip["start_time"]
        end = clip["end_time"]
        out_path = f"{OUTPUT_DIR}/clip_{clip_id}.mp4"

        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", source_video,
            "-c:v", "libx264",
            "-c:a", "aac",
            out_path,
        ]
        print(f"Cutting clip {clip_id}: {start:.1f}s - {end:.1f}s (duration: {duration:.1f}s)")
        subprocess.run(cmd, check=True)

        clip["clip_id"] = clip_id
        clip["file_path"] = out_path

    with open(clips_path, "w") as f:
        json.dump(clips, f, indent=2)

    print(f"Cut {len(clips)} clips into {OUTPUT_DIR}/")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python cut_clips.py <source_video> <clips_json> <transcript_json>")
        sys.exit(1)
    cut_clips(sys.argv[1], sys.argv[2], sys.argv[3])
