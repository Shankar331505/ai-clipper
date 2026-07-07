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
import textwrap

OUTPUT_DIR = "output"

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Liberation Sans,76,&H00FFFFFF,&H00000000,1,4,1,2,60,60,820

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

    # Group words into ~3-word chunks for readable on-screen captions
    chunk_size = 3
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if not chunk:
            continue

        chunk_start = chunk[0]["start"] - clip_start
        chunk_end = chunk[-1]["end"] - clip_start

        # Generate separate subtitle events for each word in the chunk to achieve highlight animation
        for j in range(len(chunk)):
            seg_start = chunk[j]["start"] - clip_start if j > 0 else chunk_start
            seg_end = chunk[j+1]["start"] - clip_start if j < len(chunk) - 1 else chunk_end

            # Ensure start < end
            if seg_start >= seg_end:
                seg_end = seg_start + 0.1

            text_parts = []
            for idx, w in enumerate(chunk):
                word_str = w["word"].strip().upper()
                if idx == j:
                    # Highlight the spoken word in bright neon green (&H2BFB3E&)
                    text_parts.append(f"{{\\c&H2BFB3E&}}{word_str}{{\\c&HFFFFFF&}}")
                else:
                    text_parts.append(word_str)

            formatted_text = " ".join(text_parts)
            lines.append(
                f"Dialogue: 0,{seconds_to_ass_time(seg_start)},{seconds_to_ass_time(seg_end)},Default,{formatted_text}"
            )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))



def burn_captions(video_path: str, ass_path: str, title_text: str, output_path: str):
    vf_filter = f"ass={ass_path}"

    temp_title_path = None
    if title_text:
        # Wrap title text to fit within the box (max 32 chars per line)
        wrapped_title = "\n".join(textwrap.wrap(title_text, width=32))

        # Save to a temp file to avoid escaping issues in FFmpeg drawtext
        temp_title_path = f"temp_title_{os.path.basename(output_path)}.txt"
        with open(temp_title_path, "w", encoding="utf-8") as f:
            f.write(wrapped_title)

        # drawtext: white box, black bold text, centered in the top 420px black bar
        drawtext_filter = (
            f"drawtext=textfile={temp_title_path}:fontcolor=black:fontsize=48:"
            f"font='Liberation Sans':style=Bold:x=(w-text_w)/2:y=(420-text_h)/2:"
            f"box=1:boxcolor=white:boxborderw=20"
        )
        vf_filter = f"{drawtext_filter},{vf_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf_filter,
        "-c:a", "copy",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True)
    finally:
        if temp_title_path and os.path.exists(temp_title_path):
            try:
                os.remove(temp_title_path)
            except Exception as e:
                print(f"Warning: Failed to clean up temp title file ({e})")


def main():
    with open("clips.json") as f:
        clips = json.load(f)
    with open("transcript.json") as f:
        transcript = json.load(f)

    # Load metadata.json to map clip_id to its generated title
    metadata_map = {}
    if os.path.exists("metadata.json"):
        with open("metadata.json") as f:
            metadata = json.load(f)
            metadata_map = {item["clip_id"]: item for item in metadata}

    for clip in clips:
        clip_id = clip["clip_id"]
        reframed_path = f"{OUTPUT_DIR}/reframed_{clip_id}.mp4"
        if not os.path.exists(reframed_path):
            print(f"Skipping {clip_id}, reframed file not found")
            continue

        ass_path = f"{OUTPUT_DIR}/captions_{clip_id}.ass"
        final_path = f"{OUTPUT_DIR}/final_{clip_id}.mp4"

        # Get generated title for the headline banner
        meta = metadata_map.get(clip_id, {})
        title_text = meta.get("title", "")

        build_ass_for_clip(transcript, clip["start_time"], clip["end_time"], ass_path)
        burn_captions(reframed_path, ass_path, title_text, final_path)

        clip["final_path"] = final_path
        print(f"Captioned -> {final_path}")


    with open("clips.json", "w") as f:
        json.dump(clips, f, indent=2)


if __name__ == "__main__":
    main()
