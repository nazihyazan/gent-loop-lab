# Ghost Mannequin Catwalk Video Generator (Cloud Studio)

AI & 3D Runway Simulation System that transforms flat dress/garment photos into realistic Ghost Mannequin Catwalk Fashion Videos without loading your local computer.

---

## Features

- **True Ghost Mannequin Illusion**: Hollow neckline and hood, complete pitch-black void inside, no head or face visible.
- **Runway Fashion Stage**: Reflective glossy catwalk floor, overhead truss spotlights, dark stage backdrop.
- **Fluid Catwalk Walk Cycle**: Walking forward down the runway, turning pose, and walking back.
- **100% Cloud Rendering (GitHub Actions)**: Renders directly on GitHub's cloud servers for free without freezing or slowing down your local machine.
- **Vertical 9:16 Video**: Formatted for mobile fashion showcases, TikTok, Instagram Reels, and eCommerce displays (720x1280).

---

## Project Structure

```
.
├── .github/workflows/
│   └── generate_catwalk.yml       # Automated GitHub Actions cloud render pipeline
├── inputs/
│   └── dress.jpg                  # Input dress / jalaba / kaftan image
├── scripts/
│   └── ghost_mannequin_catwalk.py # Headless Blender catwalk runway engine
├── catwalk_cli.py                 # CLI orchestration tool
└── README.md
```

---

## How to Generate Video in Cloud (GitHub Actions)

### Method 1: GitHub Web Interface (1-Click)
1. Go to your repository on GitHub: `https://github.com/nazihyazan/gent-loop-lab`
2. Click on the **Actions** tab at the top.
3. In the left sidebar, click on **Ghost Mannequin Catwalk Video Generator**.
4. Click **Run workflow** on the right side.
5. Once the job completes (green checkmark), click on the run and download the video from the **Artifacts** section at the bottom (`ghost-mannequin-catwalk-video`).

### Method 2: Change Dress Photo
1. Upload your new garment photo to `inputs/dress.jpg` (or commit it).
2. The workflow will automatically trigger, render the walking video, and output the download link in Actions.

---

## Local Usage (Optional)

If you have Blender installed locally and want to test offline:

```bash
python3 catwalk_cli.py --image inputs/dress.jpg --color "#5c4046" --frames 120 --output renders/catwalk.mp4
```
