"""
Reframe each cut clip from 16:9 to 9:16 using face-detection-guided cropping.
Downloads a DIFFERENT random gameplay video for each clip from the gameplay file
(which contains multiple YouTube links, one per line) and picks a random time
offset within that gameplay video.

Usage: python reframe.py
(reads all clip_*.mp4 files from output/, writes reframed_*.mp4 in place)
"""
import glob
import os
import subprocess
import cv2
import mediapipe as mp
import numpy as np
import random
import json

OUTPUT_DIR = "output"
GAMEPLAY_FILE = "gameplay"
GAMEPLAY_CACHE_DIR = "gameplay_cache"

os.makedirs(GAMEPLAY_CACHE_DIR, exist_ok=True)


def get_video_duration(video_path: str) -> float:
    """Returns the duration of the video in seconds using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0:
        return float(frames / fps)
    return 0.0


def load_gameplay_links() -> list:
    """Load gameplay video links from the gameplay file (one URL per line)."""
    if not os.path.exists(GAMEPLAY_FILE):
        return []
    with open(GAMEPLAY_FILE) as f:
        links = [line.strip() for line in f if line.strip()]
    return links


def download_gameplay(url: str, index: int) -> str:
    """Download a gameplay video and cache it. Returns the path to the downloaded file."""
    cached_path = f"{GAMEPLAY_CACHE_DIR}/gameplay_{index:03d}.mp4"

    if os.path.exists(cached_path):
        print(f"Using cached gameplay: {cached_path}")
        return cached_path

    print(f"Downloading gameplay video {index}: {url}")

    if "youtube.com" in url or "youtu.be" in url:
        # Use yt-dlp for YouTube links
        cookies_arg = ["--cookies", "cookies.txt"] if os.path.exists("cookies.txt") else []
        cmd = [
            "yt-dlp", "--no-cache-dir",
            *cookies_arg,
            "--extractor-args", "youtube:player_client=web_safari,web",
            "--remote-components", "ejs:github",
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "-o", cached_path,
            url,
        ]
    else:
        # Assume Google Drive or direct link
        cmd = ["gdown", url, "-O", cached_path]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to download gameplay {index}: {e}")
        return ""

    return cached_path


mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)


def get_average_face_center(video_path: str) -> float:
    """Returns average horizontal face center as a fraction of width (0.0-1.0)."""
    cap = cv2.VideoCapture(video_path)
    centers = []
    frame_idx = 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sample_interval = max(1, total_frames // 50)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_interval == 0:
            h, w, _ = frame.shape
            results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.detections:
                box = results.detections[0].location_data.relative_bounding_box
                cx = box.xmin + box.width / 2
                centers.append(cx)
            if len(centers) >= 25:
                break
        frame_idx += 1

    cap.release()

    if not centers:
        return 0.5
    return float(np.mean(centers))


def reframe_clip(input_path: str, output_path: str, gameplay_path: str = None):
    center_frac = get_average_face_center(input_path)
    print(f"{input_path}: average face center at {center_frac:.2f} of width")

    if gameplay_path and os.path.exists(gameplay_path):
        print(f"Using gameplay: {gameplay_path}")

        clip_dur = get_video_duration(input_path)
        gp_dur = get_video_duration(gameplay_path)

        # Random offset within gameplay video, ensuring enough length for the clip
        max_start = max(0.0, gp_dur - clip_dur - 2.0)
        gp_start = random.uniform(0.0, max_start) if max_start > 0 else 0.0
        print(f"  Gameplay offset: {gp_start:.1f}s (of {gp_dur:.1f}s total)")

        filter_complex = (
            f"[0:v]crop=ih*3/2:ih:max(0\\,min(iw-ih*3/2\\,iw*{center_frac}-ih*3/4)):0,scale=1080:720[top];"
            f"[1:v]scale=1080:720:force_original_aspect_ratio=increase,crop=1080:720[bottom];"
            f"color=c=black:s=1080x1920[bg];"
            f"[bg][top]overlay=y=240:shortest=1[temp];"
            f"[temp][bottom]overlay=y=960[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ss", f"{gp_start:.2f}",
            "-t", f"{clip_dur:.2f}",
            "-i", gameplay_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
            "-c:a", "copy",
            output_path,
        ]
    else:
        print("No gameplay video provided. Falling back to centered-square layout.")
        filter_complex = (
            f"[0:v]crop=ih:ih:max(0\\,min(iw-ih\\,iw*{center_frac}-ih/2)):0,scale=1080:1080[cropped];"
            "color=c=black:s=1080x1920[bg];"
            "[bg][cropped]overlay=y=(main_h-overlay_h)/2:shortest=1"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-c:a", "copy",
            output_path,
        ]

    subprocess.run(cmd, check=True)


def main():
    clip_paths = sorted(glob.glob(f"{OUTPUT_DIR}/clip_*.mp4"))
    if not clip_paths:
        print("No clips found to reframe.")
        return

    # Load gameplay links
    gameplay_links = load_gameplay_links()
    num_links = len(gameplay_links)

    if num_links == 0:
        print("No gameplay links found. Using fallback layout for all clips.")
    else:
        print(f"Found {num_links} gameplay links in '{GAMEPLAY_FILE}'")

    # Also check for single legacy gameplay.mp4
    legacy_gameplay = "gameplay.mp4" if os.path.exists("gameplay.mp4") else None

    # Assign a DIFFERENT random gameplay video to each clip
    # Shuffle the links and cycle through them so no two adjacent clips share gameplay
    if num_links > 0:
        shuffled_indices = list(range(num_links))
        random.shuffle(shuffled_indices)

    for i, clip_path in enumerate(clip_paths):
        base = os.path.basename(clip_path)
        reframed_path = f"{OUTPUT_DIR}/reframed_{base.replace('clip_', '')}"

        gameplay_path = None
        if num_links > 0:
            # Pick a different gameplay video for each clip (cycle if more clips than links)
            link_idx = shuffled_indices[i % num_links]
            url = gameplay_links[link_idx]
            gameplay_path = download_gameplay(url, link_idx)
            if not gameplay_path:
                print(f"  Download failed for link {link_idx}, trying fallback...")
                gameplay_path = legacy_gameplay
        elif legacy_gameplay:
            gameplay_path = legacy_gameplay

        reframe_clip(clip_path, reframed_path, gameplay_path)
        print(f"Reframed -> {reframed_path}")


if __name__ == "__main__":
    main()
