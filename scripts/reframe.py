"""
Reframe each cut clip from 16:9 to 9:16 using face-detection-guided cropping.
Uses a static (per-clip) crop centered on the average face position -
simpler and more reliable than frame-by-frame panning as a first version.

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

OUTPUT_DIR = "output"
GAMEPLAY_PATH = "gameplay.mp4"


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


mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)


def get_average_face_center(video_path: str) -> float:
    """Returns average horizontal face center as a fraction of width (0.0-1.0)."""
    cap = cv2.VideoCapture(video_path)
    centers = []
    frame_idx = 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    # Sample at most 50 frames uniformly to keep execution fast
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
            # Exiting early after 25 detected face coordinates is enough for an accurate average
            if len(centers) >= 25:
                break
        frame_idx += 1

    cap.release()

    if not centers:
        return 0.5  # fallback: center crop
    return float(np.mean(centers))


def reframe_clip(input_path: str, output_path: str):
    center_frac = get_average_face_center(input_path)
    print(f"{input_path}: average face center at {center_frac:.2f} of width")

    if os.path.exists(GAMEPLAY_PATH):
        # We have the gameplay background video! Stack them vertically
        print(f"Using gameplay background from: {GAMEPLAY_PATH}")

        # 1. Get durations
        clip_dur = get_video_duration(input_path)
        gp_dur = get_video_duration(GAMEPLAY_PATH)

        # 2. Select a random offset from the gameplay video
        max_start = max(0.0, gp_dur - clip_dur - 2.0)
        gp_start = random.uniform(0.0, max_start) if max_start > 0 else 0.0

        # FFmpeg filter:
        # - Top clip: Widescreen crop to 3:2 (ih*3/2 by ih) centered around face, scaled to 1080x720, overlayed at y=240 on 1080x1920 black canvas
        # - Bottom gameplay: Gameplay video scaled/cropped to exactly 1080x720, overlayed at y=960
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
            "-i", GAMEPLAY_PATH,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",  # Map only the main video's audio
            "-c:a", "copy",
            output_path,
        ]
    else:
        # Fallback to square-centered layout with black background if no gameplay video is available
        print("No gameplay file found at gameplay.mp4. Falling back to centered-square layout.")
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

    for clip_path in clip_paths:
        base = os.path.basename(clip_path)
        reframed_path = f"{OUTPUT_DIR}/reframed_{base.replace('clip_', '')}"
        reframe_clip(clip_path, reframed_path)
        print(f"Reframed -> {reframed_path}")


if __name__ == "__main__":
    main()
