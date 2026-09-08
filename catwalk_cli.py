#!/usr/bin/env python3
import subprocess
import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Ghost Mannequin Catwalk Video Generator CLI")
    parser.add_argument("--image", "-i", type=str, default="inputs/dress.jpg", help="Path to dress photo/texture")
    parser.add_argument("--color", "-c", type=str, default="#5c4046", help="Dress hex color (default #5c4046)")
    parser.add_argument("--frames", "-f", type=int, default=120, help="Number of frames (default 120 = 5s @ 24fps)")
    parser.add_argument("--width", "-w", type=int, default=720, help="Video width (default 720 for 9:16 vertical)")
    parser.add_argument("--height", "-H", type=int, default=1280, help="Video height (default 1280 for 9:16 vertical)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output MP4 file path")
    
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    catwalk_script = os.path.join(base_dir, "scripts", "ghost_mannequin_catwalk.py")
    
    if args.image and not os.path.exists(args.image):
        print(f"Warning: Image '{args.image}' not found. Falling back to default pattern.")
        
    if not args.output:
        img_name = os.path.splitext(os.path.basename(args.image))[0] if args.image and os.path.exists(args.image) else "catwalk_dress"
        args.output = os.path.join(base_dir, "renders", f"{img_name}_ghost_catwalk.mp4")
        
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    
    cmd = [
        "blender", "-b", "-P", catwalk_script, "--",
        "--output", os.path.abspath(args.output),
        "--color", args.color,
        "--frames", str(args.frames),
        "--width", str(args.width),
        "--height", str(args.height)
    ]
    if args.image and os.path.exists(args.image):
        cmd.extend(["--image", os.path.abspath(args.image)])
        
    print("=" * 60)
    print("GHOST MANNEQUIN CATWALK GENERATOR")
    print(f"Input Image: {args.image if args.image and os.path.exists(args.image) else 'Procedural Studio Texture'}")
    print(f"Dress Color: {args.color}")
    print(f"Resolution:  {args.width}x{args.height} (9:16 Vertical)")
    print(f"Frames:      {args.frames} ({round(args.frames / 24, 1)}s)")
    print(f"Output:      {args.output}")
    print("=" * 60)
    
    subprocess.run(cmd, check=True)
    print("\nRender Complete! Video successfully created at:")
    print(os.path.abspath(args.output))

if __name__ == "__main__":
    main()
