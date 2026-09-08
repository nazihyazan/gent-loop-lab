#!/usr/bin/env python3
"""
AI Video Generation Engine (Stable Video Diffusion / Image-to-Video AI)
Takes input garment photo and generates AI animated video via GPU cloud inference.
"""

import os
import sys
import argparse
import shutil

def main():
    parser = argparse.ArgumentParser(description="AI Image-to-Video Generator")
    parser.add_argument("--image", "-i", type=str, default="inputs/dress.jpg", help="Path to input garment photo")
    parser.add_argument("--output", "-o", type=str, default="renders/ai_catwalk.mp4", help="Output MP4 file path")
    parser.add_argument("--motion", "-m", type=int, default=127, help="Motion intensity (1-255, default 127)")
    parser.add_argument("--fps", type=int, default=6, help="Frames per second (default 6)")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Input image '{args.image}' not found.")
        sys.exit(1)

    print("=" * 60)
    print("AI IMAGE-TO-VIDEO GENERATOR (STABLE VIDEO DIFFUSION)")
    print(f"Input Image: {args.image}")
    print(f"Motion ID:   {args.motion}")
    print(f"FPS:         {args.fps}")
    print(f"Output File: {args.output}")
    print("=" * 60)

    try:
        from gradio_client import Client, handle_file
    except ImportError:
        print("Installing gradio_client...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "gradio_client", "-q"], check=True)
        from gradio_client import Client, handle_file

    print("\n[1/2] Connecting to AI Video Diffusion Cloud GPU (A100)...")
    space_name = "multimodalart/stable-video-diffusion"
    client = Client(space_name)

    print("\n[2/2] Generating AI motion animation from garment photo...")
    result = client.predict(
        image=handle_file(os.path.abspath(args.image)),
        seed=42,
        randomize_seed=True,
        motion_bucket_id=args.motion,
        fps_id=args.fps,
        api_name="/video"
    )

    # Result structure: ({'video': '/tmp/.../video.mp4', 'subtitles': None}, seed)
    generated_video = None
    if isinstance(result, (tuple, list)) and len(result) > 0:
        first_item = result[0]
        if isinstance(first_item, dict) and "video" in first_item:
            generated_video = first_item["video"]
        elif isinstance(first_item, str) and os.path.exists(first_item):
            generated_video = first_item

    if not generated_video or not os.path.exists(generated_video):
        print(f"Error: Failed to retrieve generated video. Raw result: {result}")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    shutil.copy2(generated_video, os.path.abspath(args.output))

    print("\nSUCCESS: AI Video successfully generated and saved to:")
    print(os.path.abspath(args.output))

if __name__ == "__main__":
    main()
