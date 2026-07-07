"""
Generate styled .ass subtitles from Whisper word-level timestamps and burn
them into each reframed clip.

Usage: python captions.py
(reads output/reframed_*.mp4, output/../clips.json, ../transcript.json)
"""
import glob
import json
import os
import subprocess

OUTPUT_DIR = "output"

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Arial,64,&H00FFFFFF,&H00000000,1,3,1,2,60,60,120

[Events]
Format: Layer, Start, End, Style, Text
"""


def seconds_to_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def extract_all_words(transcript: dict) -> list:
    """Groq/OpenAI verbose_json responses put word timestamps either as a
    top-level 'words' list or nested under each segment - handle both."""
    if transcript.get("words"):
        return transcript["words"]
    words = []
    for seg in (transcript.get("segments") or []):
        words.extend(seg.get("words") or [])
    return words


def build_ass_for_clip(transcript: dict, clip_start: float, clip_end: float, out_path: str):
    all_words = extract_all_words(transcript)
    words = [w for w in all_words if w["start"] >= clip_start and w["end"] <= clip_end]

    lines = [ASS_HEADER]

    # Group words into ~4-word chunks for readable on-screen captions
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if not chunk:
            continue
        start = chunk[0]["start"] - clip_start
        end = chunk[-1]["end"] - clip_start
        text = " ".join(w["word"].strip() for w in chunk)
        lines.append(
            f"Dialogue: 0,{seconds_to_ass_time(start)},{seconds_to_ass_time(end)},Default,{text}"
        )

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


def burn_captions(video_path: str, ass_path: str, output_path: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass={ass_path}",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, check=True)


def main():
    with open("clips.json") as f:
        clips = json.load(f)
    with open("transcript.json") as f:
        transcript = json.load(f)

    for clip in clips:
        clip_id = clip["clip_id"]
        reframed_path = f"{OUTPUT_DIR}/reframed_{clip_id}.mp4"
        if not os.path.exists(reframed_path):
            print(f"Skipping {clip_id}, reframed file not found")
            continue

        ass_path = f"{OUTPUT_DIR}/captions_{clip_id}.ass"
        final_path = f"{OUTPUT_DIR}/final_{clip_id}.mp4"

        build_ass_for_clip(transcript, clip["start_time"], clip["end_time"], ass_path)
        burn_captions(reframed_path, ass_path, final_path)

        clip["final_path"] = final_path
        print(f"Captioned -> {final_path}")

    with open("clips.json", "w") as f:
        json.dump(clips, f, indent=2)


if __name__ == "__main__":
    main()
