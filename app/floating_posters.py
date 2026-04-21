#!/usr/bin/env python3
"""
floating_posters.py
────────────────────────────────────────────────────────────────
Fetches upcoming movie posters from Radarr and composites them
as floating, animated overlays onto a background video.

All configuration is read from environment variables.
See .env.example in the repo root for the full list.
────────────────────────────────────────────────────────────────
"""

import os
import sys
import math
import random
import tempfile
import argparse
import requests
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFilter

try:
    from moviepy.editor import VideoFileClip, ImageClip, VideoClip, CompositeVideoClip
except ImportError:
    print("ERROR: moviepy not found.  Run:  pip install moviepy")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════
#  CONFIG  —  all values read from environment variables
#             with sensible defaults
# ══════════════════════════════════════════════════════════════

def _float(key, default):
    try:
        return float(os.getenv(key, default))
    except (ValueError, TypeError):
        return float(default)

def _int(key, default):
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return int(default)

def _bool(key, default):
    val = os.getenv(key, str(default)).strip().lower()
    return val in ("1", "true", "yes")

# ── Radarr connection ─────────────────────────────────────────
RADARR_URL     = os.getenv("RADARR_URL",     "http://localhost:7878")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")

# ── File paths ────────────────────────────────────────────────
INPUT_VIDEO    = os.getenv("INPUT_VIDEO",  "/input/background.mp4")
OUTPUT_VIDEO   = os.getenv("OUTPUT_VIDEO", "/output/output.mp4")

# ── Timing ────────────────────────────────────────────────────
START_TIME      = _float("START_TIME",      2.0)
POSTER_DURATION = _float("POSTER_DURATION", 8.0)
FADE_DURATION   = _float("FADE_DURATION",   0.75)

# ── Poster selection ──────────────────────────────────────────
NUM_POSTERS    = _int("NUM_POSTERS",    4)
UPCOMING_DAYS  = _int("UPCOMING_DAYS", 180)

# ── Poster appearance ─────────────────────────────────────────
POSTER_WIDTH   = _int("POSTER_WIDTH",   185)
PADDING        = _int("PADDING",         28)
VERTICAL_POS   = _float("VERTICAL_POS",  0.52)
CORNER_RADIUS  = _int("CORNER_RADIUS",   10)

# ── Drop shadow ───────────────────────────────────────────────
ADD_SHADOW     = _bool("ADD_SHADOW", True)
SHADOW_OFFSET_X = _int("SHADOW_OFFSET_X", 7)
SHADOW_OFFSET_Y = _int("SHADOW_OFFSET_Y", 9)
SHADOW_BLUR    = _int("SHADOW_BLUR",    9)
SHADOW_OPACITY = _int("SHADOW_OPACITY", 175)

# ── Float animation ───────────────────────────────────────────
FLOAT_AMPLITUDE = _float("FLOAT_AMPLITUDE", 14.0)
FLOAT_SPEED     = _float("FLOAT_SPEED",      0.55)

# ── Output encoding ───────────────────────────────────────────
VIDEO_CRF    = os.getenv("VIDEO_CRF",    "18")
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "fast")


# ══════════════════════════════════════════════════════════════
#  RADARR API
# ══════════════════════════════════════════════════════════════

def get_upcoming_movie_entries(n: int) -> list:
    """Return up to n upcoming Radarr movies that have poster art."""
    if not RADARR_API_KEY:
        print("ERROR: RADARR_API_KEY is not set.")
        sys.exit(1)

    url     = f"{RADARR_URL}/api/v3/movie"
    headers = {"X-Api-Key": RADARR_API_KEY}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: Could not connect to Radarr at {RADARR_URL}\n  {e}")
        sys.exit(1)

    now      = datetime.now(timezone.utc)
    upcoming = []

    for m in resp.json():
        for field in ("digitalRelease", "physicalRelease", "inCinemas"):
            raw = m.get(field)
            if raw:
                try:
                    rd = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if rd > now:
                        upcoming.append({"movie": m, "release": rd})
                        break
                except (ValueError, TypeError):
                    continue

    # Only movies with a poster image
    with_poster = [
        u for u in upcoming
        if any(img.get("coverType") == "poster" for img in u["movie"].get("images", []))
    ]

    with_poster.sort(key=lambda x: x["release"])

    # Shuffle from the nearest pool for variety on repeated runs
    pool = with_poster[: max(n * 3, 15)]
    random.shuffle(pool)
    return pool[:n]


def download_poster(movie: dict, dest_path: str) -> bool:
    """Download the poster for a Radarr movie. Returns True on success."""
    poster_url = None
    for img in movie.get("images", []):
        if img.get("coverType") == "poster":
            poster_url = img.get("remoteUrl") or img.get("url")
            break

    if not poster_url:
        return False

    if poster_url.startswith("/"):
        poster_url = f"{RADARR_URL}{poster_url}"

    headers = {"X-Api-Key": RADARR_API_KEY}
    try:
        r = requests.get(poster_url, headers=headers, timeout=20, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except requests.RequestException as e:
        print(f"  ⚠  Download failed for {movie.get('title', '?')}: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  IMAGE PROCESSING
# ══════════════════════════════════════════════════════════════

def apply_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
    img  = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.width - 1, img.height - 1],
                            radius=radius, fill=255)
    img.putalpha(mask)
    return img


def add_drop_shadow(img: Image.Image) -> Image.Image:
    ox, oy  = SHADOW_OFFSET_X, SHADOW_OFFSET_Y
    extra   = SHADOW_BLUR * 2
    canvas  = Image.new("RGBA",
                        (img.width + abs(ox) + extra, img.height + abs(oy) + extra),
                        (0, 0, 0, 0))

    # Shadow: opaque black masked by poster alpha
    black = Image.new("RGBA", img.size, (0, 0, 0, SHADOW_OPACITY))
    black.putalpha(img.split()[3].point(lambda p: p * SHADOW_OPACITY // 255))

    sx, sy = extra // 2 + max(ox, 0), extra // 2 + max(oy, 0)
    canvas.paste(black, (sx, sy))
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))

    px, py = extra // 2 + max(-ox, 0), extra // 2 + max(-oy, 0)
    canvas.paste(img, (px, py), img)
    return canvas


def prepare_poster(image_path: str, target_width: int) -> Image.Image:
    img    = Image.open(image_path).convert("RGBA")
    aspect = img.height / img.width
    img    = img.resize((target_width, int(target_width * aspect)), Image.LANCZOS)
    img    = apply_rounded_corners(img, CORNER_RADIUS)
    if ADD_SHADOW:
        img = add_drop_shadow(img)
    return img


# ══════════════════════════════════════════════════════════════
#  VIDEO COMPOSITING
# ══════════════════════════════════════════════════════════════

def make_poster_clip(pil_img, pos_x: int, base_y: int, float_phase: float):
    rgba  = np.array(pil_img)             # H x W x 4  (RGBA)
    rgb   = rgba[:, :, :3]               # RGB for the visible clip
    alpha = rgba[:, :, 3] / 255.0        # normalised alpha mask (rounded corners + shadow)

    h, w  = rgb.shape[:2]
    clip  = ImageClip(rgb, ismask=False)

    def position(t):
        dy = FLOAT_AMPLITUDE * math.sin(2 * math.pi * FLOAT_SPEED * t + float_phase)
        return (pos_x, int(base_y + dy))

    def make_mask_frame(t):
        """Combine the poster alpha with a time-based fade."""
        if t < FADE_DURATION:
            fade = t / FADE_DURATION
        elif t > POSTER_DURATION - FADE_DURATION:
            fade = max(0.0, (POSTER_DURATION - t) / FADE_DURATION)
        else:
            fade = 1.0
        return alpha * fade   # preserves rounded corners + shadow transparency

    mask = VideoClip(make_mask_frame, ismask=True, duration=POSTER_DURATION)

    return (
        clip
        .set_mask(mask)
        .set_start(START_TIME)
        .set_duration(POSTER_DURATION)
        .set_position(position)
    )


def composite_video(poster_images: list, bg_path: str, out_path: str):
    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    bg            = VideoFileClip(bg_path)
    vid_w, vid_h  = bg.size
    n             = len(poster_images)
    total_width   = sum(img.width for img in poster_images) + PADDING * (n - 1)
    x_start       = (vid_w - total_width) // 2

    poster_clips  = []
    x_cursor      = x_start

    for i, img in enumerate(poster_images):
        base_y = int(vid_h * VERTICAL_POS - img.height / 2)
        base_y = max(10, min(base_y, vid_h - img.height - 10))
        phase  = (2 * math.pi * i) / n

        poster_clips.append(
            make_poster_clip(img, x_cursor, base_y, phase)
        )
        x_cursor += img.width + PADDING

    final = CompositeVideoClip([bg] + poster_clips).set_duration(bg.duration)

    print(f"\nRendering → {out_path}")
    final.write_videofile(
        out_path,
        codec         = "libx264",
        audio_codec   = "aac",
        fps           = bg.fps,
        preset        = VIDEO_PRESET,
        ffmpeg_params = ["-crf", VIDEO_CRF],
        logger        = "bar",
    )
    bg.close()
    final.close()


# ══════════════════════════════════════════════════════════════
#  CLI OVERRIDES
# ══════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Overlay floating Radarr posters onto a background video."
    )
    p.add_argument("--input",    help="Background video path")
    p.add_argument("--output",   help="Output video path")
    p.add_argument("--start",    type=float, help="Start time in seconds")
    p.add_argument("--duration", type=float, help="Poster visible duration (max 10)")
    p.add_argument("--count",    type=int,   help="Number of posters (1–6)")
    p.add_argument("--width",    type=int,   help="Poster width in pixels")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    global INPUT_VIDEO, OUTPUT_VIDEO, START_TIME, POSTER_DURATION, NUM_POSTERS, POSTER_WIDTH
    if args.input:                INPUT_VIDEO     = args.input
    if args.output:               OUTPUT_VIDEO    = args.output
    if args.start    is not None: START_TIME      = args.start
    if args.duration is not None: POSTER_DURATION = min(args.duration, 10.0)
    if args.count    is not None: NUM_POSTERS     = max(1, min(args.count, 6))
    if args.width    is not None: POSTER_WIDTH    = args.width

    if POSTER_DURATION > 10:
        print("⚠  POSTER_DURATION capped at 10 seconds.")
        POSTER_DURATION = 10.0

    if not Path(INPUT_VIDEO).exists():
        print(f"ERROR: Input video not found: {INPUT_VIDEO}")
        sys.exit(1)

    print("─" * 52)
    print(f"  Radarr:    {RADARR_URL}")
    print(f"  Input:     {INPUT_VIDEO}")
    print(f"  Output:    {OUTPUT_VIDEO}")
    print(f"  Posters:   {NUM_POSTERS}  (start: {START_TIME}s  show: {POSTER_DURATION}s)")
    print("─" * 52)

    # 1 ── Fetch upcoming movies
    print(f"\nFetching {NUM_POSTERS} upcoming movies from Radarr...")
    entries = get_upcoming_movie_entries(NUM_POSTERS)

    if not entries:
        print("No upcoming movies with posters found in Radarr.")
        sys.exit(1)

    print(f"Selected {len(entries)} movies:")
    for e in entries:
        m = e["movie"]
        print(f"  • {m['title']}  ({e['release'].strftime('%b %d, %Y')})")

    # 2 ── Download and prepare posters
    poster_images = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, e in enumerate(entries):
            m    = e["movie"]
            path = os.path.join(tmpdir, f"poster_{i}.jpg")
            print(f"  ↓  {m['title']}")
            if download_poster(m, path):
                poster_images.append(prepare_poster(path, POSTER_WIDTH))
            else:
                print(f"     (skipped — no poster available)")

        if not poster_images:
            print("\nERROR: No posters downloaded successfully.")
            sys.exit(1)

        # 3 ── Composite
        composite_video(poster_images, INPUT_VIDEO, OUTPUT_VIDEO)

    print(f"\n✅  Done!  Output saved to:\n   {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()
