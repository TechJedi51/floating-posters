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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from moviepy.editor import VideoFileClip, ImageClip, VideoClip, CompositeVideoClip
except ImportError:
    print("ERROR: moviepy not found.  Run:  pip install moviepy")
    sys.exit(1)


VERSION = "1.4.0"

# ══════════════════════════════════════════════════════════════
#  CONFIG  —  all values read from environment variables
# ══════════════════════════════════════════════════════════════

def _float(key, default):
    try:    return float(os.getenv(key, default))
    except: return float(default)

def _int(key, default):
    try:    return int(os.getenv(key, default))
    except: return int(default)

def _bool(key, default):
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")

# ── Radarr ────────────────────────────────────────────────────
RADARR_URL     = os.getenv("RADARR_URL",     "http://localhost:7878")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")

# ── File paths ────────────────────────────────────────────────
INPUT_VIDEO  = os.getenv("INPUT_VIDEO",  "/input/background.mp4")
OUTPUT_VIDEO = os.getenv("OUTPUT_VIDEO", "/output/output.mp4")

# ── Timing ────────────────────────────────────────────────────
START_TIME      = _float("START_TIME",      2.0)
POSTER_DURATION = _float("POSTER_DURATION", 8.0)
FADE_DURATION   = _float("FADE_DURATION",   0.75)

# ── Poster selection ──────────────────────────────────────────
NUM_POSTERS   = _int("NUM_POSTERS",    4)
UPCOMING_DAYS = _int("UPCOMING_DAYS", 180)

# ── Poster appearance ─────────────────────────────────────────
POSTER_WIDTH  = _int("POSTER_WIDTH",   185)
PADDING       = _int("PADDING",         28)
VERTICAL_POS  = _float("VERTICAL_POS",  0.52)
CORNER_RADIUS = _int("CORNER_RADIUS",   10)

# ── Drop shadow ───────────────────────────────────────────────
ADD_SHADOW      = _bool("ADD_SHADOW", True)
SHADOW_OFFSET_X = _int("SHADOW_OFFSET_X", 7)
SHADOW_OFFSET_Y = _int("SHADOW_OFFSET_Y", 9)
SHADOW_BLUR     = _int("SHADOW_BLUR",     9)
SHADOW_OPACITY  = _int("SHADOW_OPACITY", 175)

# ── Float animation ───────────────────────────────────────────
FLOAT_AMPLITUDE = _float("FLOAT_AMPLITUDE", 14.0)
FLOAT_SPEED     = _float("FLOAT_SPEED",      0.55)

# ── Output encoding ───────────────────────────────────────────
VIDEO_CRF    = os.getenv("VIDEO_CRF",    "18")
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "fast")
CPU_THREADS  = _int("CPU_THREADS", 2)

# ── Release date label ────────────────────────────────────────
SHOW_RELEASE_DATE   = _bool("SHOW_RELEASE_DATE",  True)
RELEASE_DATE_COLOR  = os.getenv("RELEASE_DATE_COLOR",  "#FFFFFF")
RELEASE_DATE_SIZE   = _int("RELEASE_DATE_SIZE",   15)
RELEASE_DATE_SHADOW = _bool("RELEASE_DATE_SHADOW", True)

# ── Font ─────────────────────────────────────────────────────
FONT = os.getenv("FONT", "Poppins-Bold")

# ── Bottom message ────────────────────────────────────────────
BOTTOM_MESSAGE_SHOW     = _bool("BOTTOM_MESSAGE_SHOW", False)
BOTTOM_MESSAGE          = os.getenv("BOTTOM_MESSAGE", "")
BOTTOM_MESSAGE_ADD_DATE = _bool("BOTTOM_MESSAGE_ADD_DATE", True)
BOTTOM_MESSAGE_COLOR    = os.getenv("BOTTOM_MESSAGE_COLOR", "white")
BOTTOM_MESSAGE_SIZE     = _int("BOTTOM_MESSAGE_SIZE", 15)
BOTTOM_MESSAGE_SHADOW   = _bool("BOTTOM_MESSAGE_SHADOW", False)

# ── Top message ───────────────────────────────────────────────
TOP_MESSAGE_SHOW     = _bool("TOP_MESSAGE_SHOW", False)
TOP_MESSAGE          = os.getenv("TOP_MESSAGE", "")
TOP_MESSAGE_ADD_DATE = _bool("TOP_MESSAGE_ADD_DATE", False)
TOP_MESSAGE_COLOR    = os.getenv("TOP_MESSAGE_COLOR", "white")
TOP_MESSAGE_SIZE     = _int("TOP_MESSAGE_SIZE", 15)
TOP_MESSAGE_SHADOW   = _bool("TOP_MESSAGE_SHADOW", False)


# ══════════════════════════════════════════════════════════════
#  RADARR API
# ══════════════════════════════════════════════════════════════

def get_upcoming_movie_entries(n: int) -> list:
    if not RADARR_API_KEY:
        print("ERROR: RADARR_API_KEY is not set.")
        sys.exit(1)

    headers = {"X-Api-Key": RADARR_API_KEY}
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/movie", headers=headers, timeout=15)
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

    with_poster = [
        u for u in upcoming
        if any(img.get("coverType") == "poster" for img in u["movie"].get("images", []))
    ]
    with_poster.sort(key=lambda x: x["release"])

    pool = with_poster[: max(n * 3, 15)]
    random.shuffle(pool)
    return pool[:n]


def download_poster(movie: dict, dest_path: str) -> bool:
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
#  FONTS & TEXT RENDERING
# ══════════════════════════════════════════════════════════════

# All fonts available in the container.
# Set FONT=<name> in docker-compose to pick one.
FONT_MAP = {
    # ── Poppins (Google Fonts — downloaded in Dockerfile) ─────
    "Poppins-Bold":             "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "Poppins-Medium":           "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "Poppins-Regular":          "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    # ── DejaVu (fonts-dejavu-core) ────────────────────────────
    "DejaVuSans-Bold":          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans":               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSerif-Bold":         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "DejaVuSerif":              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "DejaVuSansMono-Bold":      "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "DejaVuSansCondensed-Bold": "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    # ── Liberation (fonts-liberation) ─────────────────────────
    "LiberationSans-Bold":      "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "LiberationSans":           "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "LiberationSerif-Bold":     "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "LiberationMono-Bold":      "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    # ── FreeFonts (fonts-freefont-ttf) ────────────────────────
    "FreeSansBold":             "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "FreeSerifBold":            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    # ── Crosextra (fonts-crosextra-*) ─────────────────────────
    "Carlito-Bold":             "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
    "Caladea-Bold":             "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
    # ── macOS fallbacks (running locally without Docker) ──────
    "Helvetica":                "/System/Library/Fonts/Helvetica.ttc",
    "HelveticaNeue":            "/System/Library/Fonts/HelveticaNeue.ttc",
}

def load_font(size: int) -> ImageFont.ImageFont:
    """Load the font named by FONT env var, falling back through available fonts."""
    # Try the requested font first
    if FONT in FONT_MAP:
        path = FONT_MAP[FONT]
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                print(f"  [font] {FONT}  size={size}")
                return font
            except Exception as e:
                print(f"  [font] {FONT} failed ({e}), trying fallbacks...")
        else:
            print(f"  [font] {FONT} not found at {path}, trying fallbacks...")

    # Walk the full map in order until one loads
    for name, path in FONT_MAP.items():
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, size)
                print(f"  [font] {name} (fallback)  size={size}")
                return font
            except Exception:
                continue

    print(f"  [font] PIL built-in fallback  size={size}")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _parse_color(color_str: str) -> tuple:
    try:
        return Image.new("RGBA", (1, 1), color_str).getpixel((0, 0))[:3]
    except Exception:
        return (255, 255, 255)


def make_text_image(text: str, font_size: int, color: str, shadow: bool) -> Image.Image:
    """
    Render text as a PIL RGBA image with a semi-transparent rounded pill
    background. Readable against any video background colour.
    """
    font       = load_font(font_size)
    text_color = _parse_color(color)

    # Measure on a generously-sized scratch canvas
    scratch = Image.new("RGBA", (4000, font_size * 6), (0, 0, 0, 0))
    d       = ImageDraw.Draw(scratch)
    bbox    = d.textbbox((0, 0), text, font=font)
    text_w  = bbox[2] - bbox[0]
    text_h  = bbox[3] - bbox[1]

    h_pad = 12
    v_pad = 6
    img_w = text_w + h_pad * 2
    img_h = text_h + v_pad * 2

    img  = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Semi-transparent dark pill
    draw.rounded_rectangle([(0, 0), (img_w - 1, img_h - 1)],
                            radius=6, fill=(0, 0, 0, 170))

    # Compensate for font bearing offsets so text sits inside the pill
    tx = h_pad - bbox[0]
    ty = v_pad - bbox[1]

    if shadow:
        draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 220))

    draw.text((tx, ty), text, font=font, fill=(*text_color, 255))

    print(f"  [text] '{text}'  {img_w}x{img_h}px")
    return img


# ══════════════════════════════════════════════════════════════
#  POSTER IMAGE PROCESSING
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
    ox, oy = SHADOW_OFFSET_X, SHADOW_OFFSET_Y
    extra  = SHADOW_BLUR * 2
    canvas = Image.new("RGBA",
                       (img.width + abs(ox) + extra, img.height + abs(oy) + extra),
                       (0, 0, 0, 0))
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
#  CLIP FACTORIES
# ══════════════════════════════════════════════════════════════

def _rgba_to_clip(pil_img: Image.Image,
                  pos_x: int,
                  pos_y,          # int (static) or callable(t)->float
                  start: float,
                  duration: float) -> ImageClip:
    """
    Core factory: wraps any RGBA PIL image as a moviepy clip.
    Alpha channel drives the mask; fades in/out over FADE_DURATION.
    pos_y may be a static int or a function of time for animation.
    """
    arr   = np.array(pil_img.convert("RGBA"))
    rgb   = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0

    clip     = ImageClip(rgb, ismask=False)
    is_static = isinstance(pos_y, (int, float))

    def position(t):
        y = pos_y if is_static else pos_y(t)
        return (pos_x, int(y))

    def mask_frame(t):
        if t < FADE_DURATION:
            fade = t / FADE_DURATION
        elif t > duration - FADE_DURATION:
            fade = max(0.0, (duration - t) / FADE_DURATION)
        else:
            fade = 1.0
        return alpha * fade

    mask = VideoClip(mask_frame, ismask=True, duration=duration)

    return (
        clip
        .set_mask(mask)
        .set_start(start)
        .set_duration(duration)
        .set_position(position)
    )


def make_poster_clip(pil_img, pos_x, base_y, float_phase):
    def y_fn(t):
        return base_y + FLOAT_AMPLITUDE * math.sin(
            2 * math.pi * FLOAT_SPEED * t + float_phase)
    return _rgba_to_clip(pil_img, pos_x, y_fn, START_TIME, POSTER_DURATION)


def make_date_clip(date_text, center_x, poster_bottom_y, float_phase):
    """Date label that floats in sync with its poster, 6px below it."""
    img   = make_text_image(date_text, RELEASE_DATE_SIZE,
                            RELEASE_DATE_COLOR, RELEASE_DATE_SHADOW)
    pos_x = center_x - img.width // 2
    gap   = 6

    def y_fn(t):
        drift = FLOAT_AMPLITUDE * math.sin(2 * math.pi * FLOAT_SPEED * t + float_phase)
        return poster_bottom_y + gap + drift

    return _rgba_to_clip(img, pos_x, y_fn, START_TIME, POSTER_DURATION)


def make_bottom_message_clip(message, vid_w, vid_h):
    """Centered, non-floating message 24px from the bottom edge."""
    img   = make_text_image(message, BOTTOM_MESSAGE_SIZE,
                            BOTTOM_MESSAGE_COLOR, shadow=BOTTOM_MESSAGE_SHADOW)
    pos_x = (vid_w - img.width) // 2
    pos_y = vid_h - img.height - 24
    return _rgba_to_clip(img, pos_x, pos_y, START_TIME, POSTER_DURATION)


def make_top_message_clip(message, vid_w, vid_h):
    """Centered, non-floating message 24px from the top edge."""
    img   = make_text_image(message, TOP_MESSAGE_SIZE,
                            TOP_MESSAGE_COLOR, shadow=TOP_MESSAGE_SHADOW)
    pos_x = (vid_w - img.width) // 2
    pos_y = 24
    return _rgba_to_clip(img, pos_x, pos_y, START_TIME, POSTER_DURATION)


# ══════════════════════════════════════════════════════════════
#  VIDEO COMPOSITING
# ══════════════════════════════════════════════════════════════

def composite_video(poster_data: list, bg_path: str, out_path: str):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    bg           = VideoFileClip(bg_path)
    vid_w, vid_h = bg.size
    n            = len(poster_data)
    total_width  = sum(d["img"].width for d in poster_data) + PADDING * (n - 1)
    x_start      = (vid_w - total_width) // 2

    all_clips = [bg]
    x_cursor  = x_start

    for i, d in enumerate(poster_data):
        img   = d["img"]
        phase = (2 * math.pi * i) / n

        base_y = int(vid_h * VERTICAL_POS - img.height / 2)
        base_y = max(10, min(base_y, vid_h - img.height - 10))

        all_clips.append(make_poster_clip(img, x_cursor, base_y, phase))

        if SHOW_RELEASE_DATE and d["date"]:
            center_x      = x_cursor + img.width // 2
            poster_bottom = base_y + img.height
            all_clips.append(
                make_date_clip(d["date"], center_x, poster_bottom, phase)
            )

        x_cursor += img.width + PADDING

    # Bottom message
    if BOTTOM_MESSAGE_SHOW and (BOTTOM_MESSAGE or BOTTOM_MESSAGE_ADD_DATE):
        msg = BOTTOM_MESSAGE
        if BOTTOM_MESSAGE_ADD_DATE:
            now     = datetime.now()
            datestr = f"{now.strftime('%B')} {now.day}, {now.year}"
            msg     = f"{msg}  {datestr}".strip() if msg else datestr
        print(f"  [bottom msg] '{msg}'")
        all_clips.append(make_bottom_message_clip(msg, vid_w, vid_h))

    # Top message
    if TOP_MESSAGE_SHOW and (TOP_MESSAGE or TOP_MESSAGE_ADD_DATE):
        msg = TOP_MESSAGE
        if TOP_MESSAGE_ADD_DATE:
            now     = datetime.now()
            datestr = f"{now.strftime('%B')} {now.day}, {now.year}"
            msg     = f"{msg}  {datestr}".strip() if msg else datestr
        print(f"  [top msg] '{msg}'")
        all_clips.append(make_top_message_clip(msg, vid_w, vid_h))

    final = CompositeVideoClip(all_clips).set_duration(bg.duration)

    thread_str = str(CPU_THREADS) if CPU_THREADS > 0 else "0"
    print(f"\nRendering → {out_path}  (threads: {thread_str})")
    final.write_videofile(
        out_path,
        codec         = "libx264",
        audio_codec   = "aac",
        fps           = bg.fps,
        preset        = VIDEO_PRESET,
        ffmpeg_params = ["-threads", thread_str, "-crf", VIDEO_CRF],
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

    print("─" * 54)
    print(f"  floating-posters  v{VERSION}")
    print(f"  Radarr:    {RADARR_URL}")
    print(f"  Input:     {INPUT_VIDEO}")
    print(f"  Output:    {OUTPUT_VIDEO}")
    print(f"  Posters:   {NUM_POSTERS}  start={START_TIME}s  show={POSTER_DURATION}s")
    print(f"  Date:      {'on' if SHOW_RELEASE_DATE else 'off'}"
          f"    Msg: {'on' if BOTTOM_MESSAGE_SHOW else 'off'}"
          f"    Threads: {CPU_THREADS}")
    print("─" * 54)

    # 1 ── Fetch upcoming movies
    print(f"\nFetching {NUM_POSTERS} upcoming movies from Radarr...")
    entries = get_upcoming_movie_entries(NUM_POSTERS)

    if not entries:
        print("No upcoming movies with posters found in Radarr.")
        sys.exit(1)

    print(f"Selected {len(entries)} movies:")
    for e in entries:
        m  = e["movie"]
        rd = e["release"]
        print(f"  • {m['title']}  ({rd.strftime('%B')} {rd.day}, {rd.year})")

    # 2 ── Download and prepare posters
    poster_data = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, e in enumerate(entries):
            m    = e["movie"]
            path = os.path.join(tmpdir, f"poster_{i}.jpg")
            print(f"  ↓  {m['title']}")
            if download_poster(m, path):
                rd       = e["release"]
                date_str = (f"{rd.strftime('%B')} {rd.day}, {rd.year}"
                            if SHOW_RELEASE_DATE else "")
                poster_data.append({
                    "img":  prepare_poster(path, POSTER_WIDTH),
                    "date": date_str,
                })
            else:
                print(f"     (skipped — no poster available)")

        if not poster_data:
            print("\nERROR: No posters downloaded successfully.")
            sys.exit(1)

        # 3 ── Composite
        composite_video(poster_data, INPUT_VIDEO, OUTPUT_VIDEO)

    print(f"\n✅  Done!  Output saved to:\n   {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()
