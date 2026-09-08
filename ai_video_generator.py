#!/usr/bin/env python3
"""
Advanced AI Video Generator (Wan 2.1 / Wan 2.2 I2V Lightning Engine)
High-end AI Video Generation with Prompt & Image Conditioning.
"""

import os
import sys
import argparse
import shutil

def main():
    parser = argparse.ArgumentParser(description="Wan 2.2 / Advanced AI Video Generator")
    parser.add_argument("--image", "-i", type=str, default="inputs/dress.jpg", help="Path to input garment photo")
    parser.add_argument("--prompt", "-p", type=str, 
                        default="Fashion runway catwalk show, ghost mannequin wearing this Moroccan hooded jalaba walking forward down the runway, invisible void head, glossy reflective floor, dramatic fashion spotlights",
                        help="Text prompt describing the scene and motion")
    parser.add_argument("--negative-prompt", "-np", type=str,
                        default="blurry, low quality, deformed, face, head, watermark, shaky camera",
                        help="Negative prompt")
    parser.add_argument("--steps", "-s", type=int, default=4, help="Inference steps (default 4)")
    parser.add_argument("--duration", "-d", type=float, default=3.5, help="Duration in seconds (default 3.5)")
    parser.add_argument("--output", "-o", type=str, default="renders/wan_ai_dress_catwalk.mp4", help="Output MP4 file path")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Input image '{args.image}' not found.")
        sys.exit(1)

    print("=" * 65)
    print("ADVANCED AI VIDEO GENERATOR (WAN 2.2 I2V LIGHTNING)")
    print(f"Input Image: {args.image}")
    print(f"Prompt:      {args.prompt}")
    print(f"Steps:       {args.steps}")
    print(f"Duration:    {args.duration}s")
    print(f"Output File: {args.output}")
    print("=" * 65)

    try:
        from gradio_client import Client, handle_file
    except ImportError:
        print("Installing gradio_client...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "gradio_client", "-q"], check=True)
        from gradio_client import Client, handle_file

    generated_video = None

    # Primary Engine: Wan 2.2 I2V Lightning (State-of-the-Art 14B Video Diffusion)
    try:
        print("\n[1/2] Connecting to Wan 2.2 I2V Cloud GPU...")
        client = Client("Saravutw/WAN2.2_I2V_LIGHTNING_4-8step_custom")
        print("[2/2] Generating photorealistic video with image + prompt conditioning...")
        res = client.predict(
            input_image=handle_file(os.path.abspath(args.image)),
            last_image=handle_file(os.path.abspath(args.image)),
            prompt=args.prompt,
            steps=args.steps,
            negative_prompt=args.negative_prompt,
            duration_seconds=args.duration,
            guidance_scale=1.0,
            guidance_scale_2=1.0,
            seed=42,
            randomize_seed=True,
            quality=5,
            scheduler="UniPCMultistep",
            flow_shift=3.0,
            frame_multiplier=16,
            safe_mode=False,
            video_component=True,
            api_name="/generate_video"
        )
        if isinstance(res, (tuple, list)) and len(res) > 0 and os.path.exists(str(res[0])):
            generated_video = res[0]
    except Exception as e:
        print(f"Wan 2.2 primary engine notice: {e}")

    # Fallback Engine: Stable Video Diffusion
    if not generated_video or not os.path.exists(generated_video):
        print("\nSwitching to Stable Video Diffusion (SVD) High-Res Engine...")
        try:
            svd_client = Client("multimodalart/stable-video-diffusion")
            svd_res = svd_client.predict(
                image=handle_file(os.path.abspath(args.image)),
                seed=42,
                randomize_seed=True,
                motion_bucket_id=127,
                fps_id=6,
                api_name="/video"
            )
            if isinstance(svd_res, (tuple, list)) and len(svd_res) > 0:
                first_item = svd_res[0]
                if isinstance(first_item, dict) and "video" in first_item:
                    generated_video = first_item["video"]
                elif isinstance(first_item, str) and os.path.exists(first_item):
                    generated_video = first_item
        except Exception as e2:
            print(f"SVD engine error: {e2}")

    if not generated_video or not os.path.exists(generated_video):
        print("Error: Could not generate video from AI engines.")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    shutil.copy2(generated_video, os.path.abspath(args.output))

    print("\nSUCCESS: High-End AI Video generated and saved to:")
    print(os.path.abspath(args.output))

if __name__ == "__main__":
    main()
