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

OUTPUT_DIR = "output"

mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)


def get_average_face_center(video_path: str) -> float:
    """Returns average horizontal face center as a fraction of width (0.0-1.0)."""
    cap = cv2.VideoCapture(video_path)
    centers = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        # Sample every 5th frame to keep this fast
        if frame_idx % 5 == 0:
            h, w, _ = frame.shape
            results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.detections:
                box = results.detections[0].location_data.relative_bounding_box
                cx = box.xmin + box.width / 2
                centers.append(cx)
        frame_idx += 1

    cap.release()

    if not centers:
        return 0.5  # fallback: center crop
    return float(np.mean(centers))


def reframe_clip(input_path: str, output_path: str):
    print(f"Reframing {input_path} to 9:16 with a blurred background to preserve all widescreen details...")

    # FFmpeg filter:
    # 1. Scale video to fill 1080x1920 and blur it -> [bg]
    # 2. Scale video to 1080 width (aspect-ratio kept, height even) -> [fg]
    # 3. Center [fg] vertically on top of [bg]
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=y=(main_h-overlay_h)/2"
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
