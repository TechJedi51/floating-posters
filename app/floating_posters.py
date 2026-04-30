#!/usr/bin/env python3
"""
floating_posters.py  —  v2.2.1
────────────────────────────────────────────────────────────────
Scans /input for video files. Each video must have a matching
.yaml file in the same directory that defines all settings.

  movie.yaml  →  Radarr (upcoming movies)
  tv.yaml     →  Sonarr (upcoming TV shows)

Global connection settings (RADARR_URL, SONARR_URL, etc.) come
from environment variables. Per-video settings come from the yaml.
────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import math
import random
import tempfile
import requests
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import yaml as _yaml
except ImportError:
    print("ERROR: pyyaml not found.  Run:  pip install pyyaml")
    sys.exit(1)

try:
    from moviepy.editor import VideoFileClip, ImageClip, VideoClip, CompositeVideoClip
except ImportError:
    print("ERROR: moviepy not found.  Run:  pip install moviepy")
    sys.exit(1)


VERSION = "2.2.1"

# ══════════════════════════════════════════════════════════════
#  GLOBAL ENV — connection / quality settings, never from yaml
# ══════════════════════════════════════════════════════════════

RADARR_URL     = os.getenv("RADARR_URL",     "http://localhost:7878")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")
SONARR_URL     = os.getenv("SONARR_URL",     "http://localhost:8989")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "")
CPU_THREADS    = int(os.getenv("CPU_THREADS", "2"))
VIDEO_CRF      = os.getenv("VIDEO_CRF",      "18")
VIDEO_PRESET   = os.getenv("VIDEO_PRESET",   "fast")
INPUT_DIR           = os.getenv("INPUT_DIR",           "/input")
OUTPUT_DIR          = os.getenv("OUTPUT_DIR",          "/output")
NEXROLL_URL         = os.getenv("NEXROLL_URL",         "")
NEXROLL_API_KEY     = os.getenv("NEXROLL_API_KEY",     "")
NEXROLL_OUTPUT_PATH = os.getenv("NEXROLL_OUTPUT_PATH", "")

# ── Startup retry ────────────────────────────────────────────
# How many times to retry connecting to Radarr/Sonarr before giving up.
# Useful when floating-posters starts before the *arr services are ready.
STARTUP_RETRY_ATTEMPTS = int(os.getenv("STARTUP_RETRY_ATTEMPTS", "5"))
STARTUP_RETRY_DELAY    = int(os.getenv("STARTUP_RETRY_DELAY",    "30"))

VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".mpg", ".mpeg", ".mkv", ".m4a"}

# ══════════════════════════════════════════════════════════════
#  PER-JOB CONFIG  —  defaults, overridden by yaml per video
# ══════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    # Poster selection
    "NUM_POSTERS":             4,
    "UPCOMING_DAYS":           180,
    # Poster appearance
    "POSTER_WIDTH":            185,
    "PADDING":                 28,
    "ROW_GAP":                 24,
    "VERTICAL_POS":            0.52,
    "CORNER_RADIUS":           10,
    # Drop shadow
    "ADD_SHADOW":              True,
    "SHADOW_OFFSET_X":         7,
    "SHADOW_OFFSET_Y":         9,
    "SHADOW_BLUR":             9,
    "SHADOW_OPACITY":          175,
    # Float animation
    "FLOAT_AMPLITUDE":         14.0,
    "FLOAT_SPEED":             0.55,
    "ANIMATION_STYLE":        "bounce",   # bounce|fade|wave|pop-in|carousel|spotlight|drift
    # Timing
    "START_TIME":              2.0,
    "POSTER_DURATION":         8.0,
    "FADE_DURATION":           0.75,
    # Font
    "FONT":                    "Poppins-Bold",
    # Release date label
    "SHOW_RELEASE_DATE":       True,
    "RELEASE_DATE_COLOR":      "#FFFFFF",
    "RELEASE_DATE_SIZE":       15,
    "RELEASE_DATE_SHADOW":     True,
    "RELEASE_DATE_BG_COLOR":   "#000000",
    "RELEASE_DATE_BG_OPACITY": 170,
    # Top message
    "TOP_MESSAGE_SHOW":        False,
    "TOP_MESSAGE":             "",
    "TOP_MESSAGE_ADD_DATE":    False,
    "TOP_MESSAGE_COLOR":       "white",
    "TOP_MESSAGE_SIZE":        15,
    "TOP_MESSAGE_SHADOW":      False,
    "TOP_MESSAGE_BG_COLOR":    "#000000",
    "TOP_MESSAGE_BG_OPACITY":  170,
    # Bottom message
    "BOTTOM_MESSAGE_SHOW":     False,
    "BOTTOM_MESSAGE":          "",
    "BOTTOM_MESSAGE_ADD_DATE": True,
    "BOTTOM_MESSAGE_COLOR":    "white",
    "BOTTOM_MESSAGE_SIZE":     15,
    "BOTTOM_MESSAGE_SHADOW":   False,
    "BOTTOM_MESSAGE_BG_COLOR": "#000000",
    "BOTTOM_MESSAGE_BG_OPACITY": 170,
    # NeXroll registration
    "NEXROLL_REGISTER":         False,
    "NEXROLL_CATEGORY":         "",
    "NEXROLL_DISPLAY_NAME":     "",
    "NEXROLL_CREATE_CATEGORY":  True,
    "NEXROLL_APPLY_TO_PLEX":    False,
}

# Module-level dict populated at the start of each job
CFG: dict = {}


def load_job_config(yaml_settings: dict):
    """Reset CFG to defaults, then apply yaml overrides with type coercion."""
    global CFG
    CFG = dict(DEFAULT_CONFIG)
    for key, raw in yaml_settings.items():
        if key not in DEFAULT_CONFIG:
            continue
        default = DEFAULT_CONFIG[key]
        val     = str(raw).strip()
        if isinstance(default, bool):
            CFG[key] = val.lower() in ("1", "true", "yes")
        elif isinstance(default, int):
            try:    CFG[key] = int(val)
            except: pass
        elif isinstance(default, float):
            try:    CFG[key] = float(val)
            except: pass
        else:
            CFG[key] = val


# ══════════════════════════════════════════════════════════════
#  YAML PARSING
# ══════════════════════════════════════════════════════════════

def parse_yaml(yaml_path: Path) -> tuple:
    """
    Parse a job yaml file.
    Returns (source_type, output_name, settings_dict)
      source_type : 'movie' | 'tv'
      output_name : value of the 'output=' entry (or stem of yaml filename)
      settings    : dict of KEY → string value for all other entries
    """
    with open(yaml_path) as f:
        data = _yaml.safe_load(f)

    source_type = None
    items       = None
    for key in ("movie", "tv"):
        if key in data:
            source_type = key
            items       = data[key] or []
            break

    if source_type is None:
        raise ValueError(f"{yaml_path.name}: top-level key must be 'movie:' or 'tv:'")

    output_name = yaml_path.stem   # fallback if output= is missing
    settings    = {}

    for item in items:
        raw = str(item).strip()
        if "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key == "output":
            output_name = val
        else:
            settings[key] = val

    return source_type, output_name, settings


# ══════════════════════════════════════════════════════════════
#  JOB DISCOVERY
# ══════════════════════════════════════════════════════════════

def find_jobs(input_dir: str) -> list:
    """
    Scan input_dir for video files. For each, look for a same-name .yaml.
    Returns list of (video_path, yaml_path) tuples, sorted by filename.
    """
    jobs = []
    for video_file in sorted(Path(input_dir).iterdir()):
        if video_file.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        yaml_file = video_file.with_suffix(".yaml")
        if not yaml_file.exists():
            print(f"  ⚠  No matching yaml for {video_file.name} — skipping")
            continue
        jobs.append((video_file, yaml_file))
    return jobs


# ══════════════════════════════════════════════════════════════
#  RADARR API
# ══════════════════════════════════════════════════════════════

def get_upcoming_movies(n: int) -> list:
    """Return up to n upcoming Radarr movies with poster art."""
    if not RADARR_API_KEY:
        print("ERROR: RADARR_API_KEY is not set.")
        sys.exit(1)

    headers = {"X-Api-Key": RADARR_API_KEY}
    resp    = None
    for attempt in range(1, STARTUP_RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(f"{RADARR_URL}/api/v3/movie", headers=headers, timeout=15)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < STARTUP_RETRY_ATTEMPTS:
                print(f"  ⚠  Radarr not ready (attempt {attempt}/{STARTUP_RETRY_ATTEMPTS}): {e}")
                print(f"     Retrying in {STARTUP_RETRY_DELAY}s...")
                time.sleep(STARTUP_RETRY_DELAY)
            else:
                print(f"ERROR: Radarr unreachable at {RADARR_URL} after {STARTUP_RETRY_ATTEMPTS} attempts\n  {e}")
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
                        upcoming.append({
                            "title":   m["title"],
                            "release": rd,
                            "images":  m.get("images", []),
                            "type":    "movie",
                        })
                        break
                except (ValueError, TypeError):
                    continue

    with_poster = [
        u for u in upcoming
        if any(img.get("coverType") == "poster" for img in u["images"])
    ]
    with_poster.sort(key=lambda x: x["release"])
    pool = with_poster[: max(n * 3, 20)]
    random.shuffle(pool)
    return pool[:n]


# ══════════════════════════════════════════════════════════════
#  SONARR API
# ══════════════════════════════════════════════════════════════

def get_upcoming_tv(n: int) -> list:
    """
    Return up to n upcoming TV series (with poster art) that have episodes
    airing within UPCOMING_DAYS. Date label is the next episode air date.
    """
    if not SONARR_API_KEY:
        print("ERROR: SONARR_API_KEY is not set.")
        sys.exit(1)

    headers = {"X-Api-Key": SONARR_API_KEY}
    now     = datetime.now(timezone.utc)
    end     = now + timedelta(days=CFG["UPCOMING_DAYS"])

    # Fetch calendar for the window
    params  = {
        "start":         now.strftime("%Y-%m-%d"),
        "end":           end.strftime("%Y-%m-%d"),
        "includeSeries": "true",
    }
    resp = None
    for attempt in range(1, STARTUP_RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(f"{SONARR_URL}/api/v3/calendar",
                                headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < STARTUP_RETRY_ATTEMPTS:
                print(f"  ⚠  Sonarr not ready (attempt {attempt}/{STARTUP_RETRY_ATTEMPTS}): {e}")
                print(f"     Retrying in {STARTUP_RETRY_DELAY}s...")
                time.sleep(STARTUP_RETRY_DELAY)
            else:
                print(f"ERROR: Sonarr unreachable at {SONARR_URL} after {STARTUP_RETRY_ATTEMPTS} attempts\n  {e}")
                sys.exit(1)

    # Collect unique series keyed by seriesId, tracking earliest air date
    series_map: dict = {}
    for ep in resp.json():
        series = ep.get("series", {})
        sid    = series.get("id")
        if not sid:
            continue
        try:
            air = datetime.fromisoformat(ep["airDateUtc"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue

        if sid not in series_map or air < series_map[sid]["release"]:
            series_map[sid] = {
                "title":   series.get("title", "Unknown"),
                "release": air,
                "images":  series.get("images", []),
                "type":    "tv",
            }

    with_poster = [
        v for v in series_map.values()
        if any(img.get("coverType") == "poster" for img in v["images"])
    ]
    with_poster.sort(key=lambda x: x["release"])
    pool = with_poster[: max(n * 3, 20)]
    random.shuffle(pool)
    return pool[:n]


# ══════════════════════════════════════════════════════════════
#  POSTER DOWNLOAD
# ══════════════════════════════════════════════════════════════

def download_poster(entry: dict, dest_path: str, source_type: str) -> bool:
    """Download the poster image for a Radarr or Sonarr entry."""
    poster_url = None
    for img in entry.get("images", []):
        if img.get("coverType") == "poster":
            poster_url = img.get("remoteUrl") or img.get("url")
            break

    if not poster_url:
        return False

    base_url = RADARR_URL if source_type == "movie" else SONARR_URL
    api_key  = RADARR_API_KEY if source_type == "movie" else SONARR_API_KEY

    if poster_url.startswith("/"):
        poster_url = f"{base_url}{poster_url}"

    headers = {"X-Api-Key": api_key}
    try:
        r = requests.get(poster_url, headers=headers, timeout=20, stream=True)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except requests.RequestException as e:
        print(f"  ⚠  Download failed for {entry.get('title', '?')}: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  FONTS & TEXT RENDERING
# ══════════════════════════════════════════════════════════════

FONT_MAP = {
    "Poppins-Bold":             "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "Poppins-Medium":           "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "Poppins-Regular":          "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "DejaVuSans-Bold":          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans":               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSerif-Bold":         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "DejaVuSerif":              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "DejaVuSansMono-Bold":      "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "DejaVuSansCondensed-Bold": "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "LiberationSans-Bold":      "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "LiberationSans":           "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "LiberationSerif-Bold":     "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "LiberationMono-Bold":      "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "FreeSansBold":             "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "FreeSerifBold":            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "Carlito-Bold":             "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
    "Caladea-Bold":             "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
    "Helvetica":                "/System/Library/Fonts/Helvetica.ttc",
    "HelveticaNeue":            "/System/Library/Fonts/HelveticaNeue.ttc",
}

_font_cache: dict = {}

def load_font(size: int) -> ImageFont.ImageFont:
    """Load the font named by CFG['FONT'], with fallback chain. Caches by (name, size)."""
    name = CFG.get("FONT", "Poppins-Bold")
    key  = (name, size)
    if key in _font_cache:
        return _font_cache[key]

    if name in FONT_MAP and Path(FONT_MAP[name]).exists():
        try:
            f = ImageFont.truetype(FONT_MAP[name], size)
            print(f"  [font] {name}  size={size}")
            _font_cache[key] = f
            return f
        except Exception as e:
            print(f"  [font] {name} failed ({e}), trying fallbacks...")

    for fname, fpath in FONT_MAP.items():
        if Path(fpath).exists():
            try:
                f = ImageFont.truetype(fpath, size)
                print(f"  [font] {fname} (fallback)  size={size}")
                _font_cache[key] = f
                return f
            except Exception:
                continue

    print(f"  [font] PIL built-in fallback  size={size}")
    try:    f = ImageFont.load_default(size=size)
    except: f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def _parse_color(color_str: str) -> tuple:
    try:
        return Image.new("RGBA", (1, 1), color_str).getpixel((0, 0))[:3]
    except Exception:
        return (255, 255, 255)


def wrap_text(text: str, font: ImageFont.ImageFont, max_px: int) -> list:
    """Word-wrap text so no line exceeds max_px. Returns list of line strings."""
    words   = text.split()
    lines   = []
    current = ""
    scratch = Image.new("RGBA", (1, 1))
    draw    = ImageDraw.Draw(scratch)

    for word in words:
        candidate = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), candidate, font=font)[2]
        if w <= max_px:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def make_text_image(text: str, font_size: int, color: str, shadow: bool,
                    bg_color: str = "#000000", bg_opacity: int = 170,
                    max_width: int = None) -> Image.Image:
    """
    Render text into a PIL RGBA image with an optional rounded pill background.
    Long text is word-wrapped if max_width is given. bg_opacity=0 = no background.
    """
    font       = load_font(font_size)
    text_color = _parse_color(color)
    bg_rgb     = _parse_color(bg_color)
    h_pad      = 12
    v_pad      = 6
    line_gap   = 4

    if max_width and max_width > h_pad * 2:
        lines = wrap_text(text, font, max_width - h_pad * 2)
    else:
        lines = [text]

    scratch = Image.new("RGBA", (8000, font_size * 6), (0, 0, 0, 0))
    d       = ImageDraw.Draw(scratch)
    bboxes  = [d.textbbox((0, 0), line, font=font) for line in lines]
    lwidths = [b[2] - b[0] for b in bboxes]
    lheights= [b[3] - b[1] for b in bboxes]

    img_w        = max(lwidths) + h_pad * 2
    total_text_h = sum(lheights) + line_gap * (len(lines) - 1)
    img_h        = total_text_h + v_pad * 2

    img  = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if bg_opacity > 0:
        draw.rounded_rectangle([(0, 0), (img_w - 1, img_h - 1)],
                                radius=6, fill=(*bg_rgb, bg_opacity))

    y_cursor = v_pad
    for line, bbox, lw, lh in zip(lines, bboxes, lwidths, lheights):
        tx = (img_w - lw) // 2 - bbox[0]
        ty = y_cursor - bbox[1]
        if shadow:
            draw.text((tx + 1, ty + 1), line, font=font, fill=(0, 0, 0, 220))
        draw.text((tx, ty), line, font=font, fill=(*text_color, 255))
        y_cursor += lh + line_gap

    print(f"  [text] '{text}'  {len(lines)} line(s)  {img_w}x{img_h}px")
    return img


# ══════════════════════════════════════════════════════════════
#  POSTER IMAGE PROCESSING
# ══════════════════════════════════════════════════════════════

def apply_rounded_corners(img: Image.Image) -> Image.Image:
    radius = CFG["CORNER_RADIUS"]
    img    = img.convert("RGBA")
    mask   = Image.new("L", img.size, 0)
    draw   = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.width - 1, img.height - 1],
                            radius=radius, fill=255)
    img.putalpha(mask)
    return img


def add_drop_shadow(img: Image.Image) -> Image.Image:
    ox, oy = CFG["SHADOW_OFFSET_X"], CFG["SHADOW_OFFSET_Y"]
    blur   = CFG["SHADOW_BLUR"]
    extra  = blur * 2
    canvas = Image.new("RGBA",
                       (img.width + abs(ox) + extra, img.height + abs(oy) + extra),
                       (0, 0, 0, 0))
    black = Image.new("RGBA", img.size, (0, 0, 0, CFG["SHADOW_OPACITY"]))
    black.putalpha(img.split()[3].point(lambda p: p * CFG["SHADOW_OPACITY"] // 255))
    sx, sy = extra // 2 + max(ox, 0), extra // 2 + max(oy, 0)
    canvas.paste(black, (sx, sy))
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=blur))
    px, py = extra // 2 + max(-ox, 0), extra // 2 + max(-oy, 0)
    canvas.paste(img, (px, py), img)
    return canvas


def prepare_poster(image_path: str) -> Image.Image:
    w      = CFG["POSTER_WIDTH"]
    img    = Image.open(image_path).convert("RGBA")
    aspect = img.height / img.width
    img    = img.resize((w, int(w * aspect)), Image.LANCZOS)
    img    = apply_rounded_corners(img)
    if CFG["ADD_SHADOW"]:
        img = add_drop_shadow(img)
    return img


# ══════════════════════════════════════════════════════════════
#  CLIP FACTORIES
# ══════════════════════════════════════════════════════════════

def _rgba_to_clip(pil_img: Image.Image, pos_x: int, pos_y,
                  start: float, duration: float) -> ImageClip:
    arr   = np.array(pil_img.convert("RGBA"))
    rgb   = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0
    clip  = ImageClip(rgb, ismask=False)

    is_static = isinstance(pos_y, (int, float))
    fade      = CFG["FADE_DURATION"]

    def position(t):
        y = pos_y if is_static else pos_y(t)
        return (pos_x, int(y))

    def mask_frame(t):
        if t < fade:
            f = t / fade
        elif t > duration - fade:
            f = max(0.0, (duration - t) / fade)
        else:
            f = 1.0
        return alpha * f

    mask = VideoClip(mask_frame, ismask=True, duration=duration)
    return (
        clip
        .set_mask(mask)
        .set_start(start)
        .set_duration(duration)
        .set_position(position)
    )


def make_poster_clip(pil_img, pos_x, base_y, float_phase):
    amp   = CFG["FLOAT_AMPLITUDE"]
    speed = CFG["FLOAT_SPEED"]
    start = CFG["START_TIME"]
    dur   = CFG["POSTER_DURATION"]

    def y_fn(t):
        return base_y + amp * math.sin(2 * math.pi * speed * t + float_phase)

    return _rgba_to_clip(pil_img, pos_x, y_fn, start, dur)


def make_date_clip(date_text, center_x, poster_bottom_y, float_phase):
    img   = make_text_image(
                date_text,
                CFG["RELEASE_DATE_SIZE"],
                CFG["RELEASE_DATE_COLOR"],
                CFG["RELEASE_DATE_SHADOW"],
                CFG["RELEASE_DATE_BG_COLOR"],
                CFG["RELEASE_DATE_BG_OPACITY"])
    pos_x = center_x - img.width // 2
    amp   = CFG["FLOAT_AMPLITUDE"]
    speed = CFG["FLOAT_SPEED"]
    gap   = 6
    start = CFG["START_TIME"]
    dur   = CFG["POSTER_DURATION"]

    def y_fn(t):
        return poster_bottom_y + gap + amp * math.sin(
            2 * math.pi * speed * t + float_phase)

    return _rgba_to_clip(img, pos_x, y_fn, start, dur)


def make_message_clip(message, vid_w, vid_h, cfg_prefix, pos_y):
    """Generic message clip factory. pos_y is a pixel int (static)."""
    img = make_text_image(
            message,
            CFG[f"{cfg_prefix}_SIZE"],
            CFG[f"{cfg_prefix}_COLOR"],
            CFG[f"{cfg_prefix}_SHADOW"],
            CFG[f"{cfg_prefix}_BG_COLOR"],
            CFG[f"{cfg_prefix}_BG_OPACITY"],
            max_width=int(vid_w * 0.85))
    pos_x = (vid_w - img.width) // 2
    return _rgba_to_clip(img, pos_x, pos_y, CFG["START_TIME"], CFG["POSTER_DURATION"])


# ══════════════════════════════════════════════════════════════
#  ROW LAYOUT
# ══════════════════════════════════════════════════════════════

def build_rows(poster_data: list) -> list:
    """
    1–5  → 1 row
    6    → 3+3
    7    → 4+3
    8    → 4+4
    9    → 5+4
    10   → 5+5
    """
    n = len(poster_data)
    if n <= 5:
        return [poster_data]
    split = math.ceil(n / 2)
    return [poster_data[:split], poster_data[split:]]



# ══════════════════════════════════════════════════════════════
#  ANIMATION STYLES
# ══════════════════════════════════════════════════════════════
#
#  bounce   — sine-wave vertical float (default)
#  fade     — static grid positions, fade in/out only
#  wave     — posters cascade in left-to-right with staggered delay
#  pop-in   — each poster scales from large down to grid size, staggered
#  carousel — elliptical rotation with depth-based scaling (3D feel)
#  spotlight— one poster at a time, large & centred, cycling through all
#  drift    — entire grid drifts slowly horizontally while fading
# ══════════════════════════════════════════════════════════════


def _fade_opacity(t: float, dur: float) -> float:
    """Standard fade-in / fade-out opacity for time t within a clip of length dur."""
    fade = CFG["FADE_DURATION"]
    if t < fade:
        return t / fade
    if t > dur - fade:
        return max(0.0, (dur - t) / fade)
    return 1.0


# ── helpers shared by full-frame styles ───────────────────────

def _paste_with_alpha(canvas: "Image.Image", img: "Image.Image",
                      cx: int, cy: int, opacity: float = 1.0):
    """Paste img (RGBA) centred on (cx, cy) onto canvas, scaling opacity."""
    if opacity <= 0:
        return
    if opacity < 1.0:
        r, g, b, a = img.split()
        a = a.point(lambda v: int(v * opacity))
        img = Image.merge("RGBA", (r, g, b, a))
    px = cx - img.width  // 2
    py = cy - img.height // 2
    canvas.paste(img, (px, py), img)


def _full_frame_clip(make_rgba, dur: float, vid_w: int, vid_h: int,
                     start: float) -> "ImageClip":
    """
    Wrap a per-frame RGBA renderer (make_rgba(t) → H×W×4 ndarray) into a
    moviepy clip with correct alpha mask.  Uses a 1-frame cache so rgb and
    mask renderers don't recompute the same frame twice.
    """
    _cache = {"t": object(), "rgba": None}

    def _get(t):
        if _cache["t"] != t:
            _cache["t"]    = t
            _cache["rgba"] = make_rgba(t)
        return _cache["rgba"]

    rgb_clip  = VideoClip(lambda t: _get(t)[:, :, :3],          duration=dur)
    mask_clip = VideoClip(lambda t: _get(t)[:, :, 3] / 255.0,   duration=dur, ismask=True)
    return rgb_clip.set_mask(mask_clip).set_start(start)


# ── BOUNCE ────────────────────────────────────────────────────

def style_bounce(poster_data, grid, vid_w, vid_h):
    """Existing sine-wave vertical float."""
    clips = []
    for d, (img, date, fx, fy, center_x, bottom_y, phase) in zip(poster_data, grid):
        amp   = CFG["FLOAT_AMPLITUDE"]
        speed = CFG["FLOAT_SPEED"]
        start = CFG["START_TIME"]
        dur   = CFG["POSTER_DURATION"]

        def y_fn(t, _fy=fy, _amp=amp, _speed=speed, _phase=phase):
            return _fy + _amp * math.sin(2 * math.pi * _speed * t + _phase)

        clips.append(_rgba_to_clip(img, fx, y_fn, start, dur))

        if CFG["SHOW_RELEASE_DATE"] and date:
            def dy_fn(t, _by=bottom_y, _amp=amp, _speed=speed, _phase=phase):
                return _by + 6 + _amp * math.sin(2 * math.pi * _speed * t + _phase)
            txt = make_text_image(date, CFG["RELEASE_DATE_SIZE"],
                                  CFG["RELEASE_DATE_COLOR"], CFG["RELEASE_DATE_SHADOW"],
                                  CFG["RELEASE_DATE_BG_COLOR"], CFG["RELEASE_DATE_BG_OPACITY"])
            clips.append(_rgba_to_clip(txt, center_x - txt.width // 2, dy_fn, start, dur))
    return clips


# ── FADE ──────────────────────────────────────────────────────

def style_fade(poster_data, grid, vid_w, vid_h):
    """Static grid positions — fade in/out only, no motion."""
    clips = []
    for d, (img, date, fx, fy, center_x, bottom_y, phase) in zip(poster_data, grid):
        start = CFG["START_TIME"]
        dur   = CFG["POSTER_DURATION"]
        clips.append(_rgba_to_clip(img, fx, fy, start, dur))
        if CFG["SHOW_RELEASE_DATE"] and date:
            txt = make_text_image(date, CFG["RELEASE_DATE_SIZE"],
                                  CFG["RELEASE_DATE_COLOR"], CFG["RELEASE_DATE_SHADOW"],
                                  CFG["RELEASE_DATE_BG_COLOR"], CFG["RELEASE_DATE_BG_OPACITY"])
            clips.append(_rgba_to_clip(txt, center_x - txt.width // 2, bottom_y + 6, start, dur))
    return clips


# ── WAVE ──────────────────────────────────────────────────────

def style_wave(poster_data, grid, vid_w, vid_h):
    """
    Posters cascade in left-to-right, each delayed by WAVE_STAGGER seconds.
    After arriving they hold position (no float).
    """
    clips     = []
    stagger   = float(os.getenv("WAVE_STAGGER", "0.3"))
    n         = len(grid)
    base_start = CFG["START_TIME"]
    fade      = CFG["FADE_DURATION"]

    for i, (d, (img, date, fx, fy, center_x, bottom_y, phase)) in             enumerate(zip(poster_data, grid)):
        delay   = i * stagger
        start   = base_start + delay
        dur     = max(CFG["POSTER_DURATION"] - delay, fade * 2 + 0.1)

        clips.append(_rgba_to_clip(img, fx, fy, start, dur))
        if CFG["SHOW_RELEASE_DATE"] and date:
            txt = make_text_image(date, CFG["RELEASE_DATE_SIZE"],
                                  CFG["RELEASE_DATE_COLOR"], CFG["RELEASE_DATE_SHADOW"],
                                  CFG["RELEASE_DATE_BG_COLOR"], CFG["RELEASE_DATE_BG_OPACITY"])
            clips.append(_rgba_to_clip(txt, center_x - txt.width // 2,
                                       bottom_y + 6, start, dur))
    return clips


# ── DRIFT ─────────────────────────────────────────────────────

def style_drift(poster_data, grid, vid_w, vid_h):
    """
    One poster at a time travels across the screen.
    Posters enter from one side and exit the other, each getting an equal
    share of POSTER_DURATION.  DRIFT_DIRECTION: left | right
    """
    direction = os.getenv("DRIFT_DIRECTION", "left")
    sign      = -1 if direction == "left" else 1
    n         = len(grid)
    total_dur = CFG["POSTER_DURATION"]
    slot_dur  = total_dur / n
    fade      = min(CFG["FADE_DURATION"], slot_dur * 0.25)
    base_start= CFG["START_TIME"]
    cy        = int(vid_h * CFG["VERTICAL_POS"])

    # Pre-render date labels
    date_imgs = []
    for _, (img, date, fx, fy, center_x, bottom_y, phase) in zip(poster_data, grid):
        if CFG["SHOW_RELEASE_DATE"] and date:
            date_imgs.append(make_text_image(
                date, CFG["RELEASE_DATE_SIZE"], CFG["RELEASE_DATE_COLOR"],
                CFG["RELEASE_DATE_SHADOW"], CFG["RELEASE_DATE_BG_COLOR"],
                CFG["RELEASE_DATE_BG_OPACITY"]))
        else:
            date_imgs.append(None)

    clips = []
    for i, (d, (img, date, fx, fy, center_x, bottom_y, phase)) in             enumerate(zip(poster_data, grid)):
        w, h   = img.width, img.height
        # Travel distance: full screen width + poster width so it fully enters and exits
        travel = vid_w + w
        speed  = travel / slot_dur

        # Entry x: just off the entering edge; exits off the opposite edge
        if sign == -1:   # moving left: enters from right
            entry_x = vid_w
        else:            # moving right: enters from left
            entry_x = -w

        start  = base_start + i * slot_dur
        poster_y = cy - h // 2

        arr   = np.array(img.convert("RGBA"))
        rgb   = arr[:, :, :3]
        alpha = arr[:, :, 3] / 255.0
        clip  = ImageClip(rgb)

        def mask_fn(t, _a=alpha, _fade=fade, _dur=slot_dur):
            return _a * _fade_opacity(t, _dur)

        def pos_fn(t, _ex=entry_x, _py=poster_y, _sign=sign, _speed=speed):
            return (int(_ex + _sign * _speed * t), _py)

        mask = VideoClip(mask_fn, ismask=True, duration=slot_dur)
        clips.append(
            clip.set_mask(mask).set_start(start).set_duration(slot_dur).set_position(pos_fn)
        )

        txt = date_imgs[i]
        if txt is not None:
            tarr  = np.array(txt.convert("RGBA"))
            tclip = ImageClip(tarr[:, :, :3])
            talpha= tarr[:, :, 3] / 255.0
            tmask = VideoClip(lambda t, _a=talpha, _dur=slot_dur: _a * _fade_opacity(t, _dur),
                              ismask=True, duration=slot_dur)
            txt_gap = poster_y + h + 6

            def tpos_fn(t, _ex=entry_x, _w=w, _tw=txt.width,
                        _py=txt_gap, _sign=sign, _speed=speed):
                # Keep date centred under poster as it moves
                poster_cx = _ex + _sign * _speed * t + _w // 2
                return (int(poster_cx - _tw // 2), _py)

            clips.append(
                tclip.set_mask(tmask).set_start(start).set_duration(slot_dur).set_position(tpos_fn)
            )

    return clips


# ── POP-IN ────────────────────────────────────────────────────

def style_popin(poster_data, grid, vid_w, vid_h):
    """
    Each poster scales from POP_SCALE (default 2.5×) down to its final size
    with an ease-out, posters arrive one by one.  After landing they hold with
    a gentle bounce.
    """
    POP_SCALE    = float(os.getenv("POPIN_SCALE",   "2.5"))
    POP_DURATION = float(os.getenv("POPIN_DURATION","1.0"))
    STAGGER      = float(os.getenv("POPIN_STAGGER", "0.3"))
    start        = CFG["START_TIME"]
    dur          = CFG["POSTER_DURATION"]
    fade         = CFG["FADE_DURATION"]
    amp          = CFG["FLOAT_AMPLITUDE"] * 0.4
    speed        = CFG["FLOAT_SPEED"]
    n            = len(grid)

    # Pre-render date labels ONCE — never call make_text_image inside make_rgba
    date_imgs = []
    for _, (img, date, fx, fy, center_x, bottom_y, phase) in zip(poster_data, grid):
        if CFG["SHOW_RELEASE_DATE"] and date:
            date_imgs.append(make_text_image(
                date, CFG["RELEASE_DATE_SIZE"], CFG["RELEASE_DATE_COLOR"],
                CFG["RELEASE_DATE_SHADOW"], CFG["RELEASE_DATE_BG_COLOR"],
                CFG["RELEASE_DATE_BG_OPACITY"]))
        else:
            date_imgs.append(None)

    def make_rgba(t):
        canvas = Image.new("RGBA", (vid_w, vid_h), (0, 0, 0, 0))
        opacity = _fade_opacity(t, dur)

        for i, (d, (img, date, fx, fy, center_x, bottom_y, phase)) in                 enumerate(zip(poster_data, grid)):
            t_off = t - i * STAGGER
            if t_off <= 0:
                continue

            w, h = img.width, img.height
            cy   = fy + h // 2

            if t_off < POP_DURATION:
                prog  = 1 - (1 - t_off / POP_DURATION) ** 3   # ease-out cubic
                scale = POP_SCALE - (POP_SCALE - 1.0) * prog
            else:
                scale = 1.0
                bounce_t = t_off - POP_DURATION
                cy = int(cy + amp * math.sin(2 * math.pi * speed * bounce_t + phase))

            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            scaled = img.resize((new_w, new_h), Image.LANCZOS)
            _paste_with_alpha(canvas, scaled, fx + w // 2, cy, opacity)

            txt = date_imgs[i]
            if txt is not None and t_off >= POP_DURATION:
                txt_cy = bottom_y + 6 + txt.height // 2 + int(
                    amp * math.sin(2 * math.pi * speed * (t_off - POP_DURATION) + phase))
                _paste_with_alpha(canvas, txt, center_x, txt_cy, opacity)

        return np.array(canvas)

    return [_full_frame_clip(make_rgba, dur, vid_w, vid_h, start)]


# ── CAROUSEL ─────────────────────────────────────────────────

def style_carousel(poster_data, grid, vid_w, vid_h):
    """
    Posters orbit an ellipse (simulated 3-D).  Front poster is largest.
    One full rotation per POSTER_DURATION so every poster is front once.
    """
    start    = CFG["START_TIME"]
    dur      = CFG["POSTER_DURATION"]
    fade     = CFG["FADE_DURATION"]
    n        = len(poster_data)

    cx       = vid_w // 2
    cy       = int(vid_h * CFG["VERTICAL_POS"])
    rx       = vid_w  * float(os.getenv("CAROUSEL_RX", "0.32"))   # horiz radius
    ry       = vid_h  * float(os.getenv("CAROUSEL_RY", "0.06"))   # depth offset
    min_sc   = float(os.getenv("CAROUSEL_MIN_SCALE", "0.45"))
    max_sc   = float(os.getenv("CAROUSEL_MAX_SCALE", "1.0"))
    rpm      = 2 * math.pi / dur   # radians per second (1 full rotation)

    init_angles = [2 * math.pi * i / n for i in range(n)]
    imgs        = [d["img"]  for d in poster_data]
    dates       = [d["date"] for d in poster_data]

    # Pre-render date labels
    date_imgs = []
    for date in dates:
        if CFG["SHOW_RELEASE_DATE"] and date:
            date_imgs.append(make_text_image(
                date, CFG["RELEASE_DATE_SIZE"], CFG["RELEASE_DATE_COLOR"],
                CFG["RELEASE_DATE_SHADOW"], CFG["RELEASE_DATE_BG_COLOR"],
                CFG["RELEASE_DATE_BG_OPACITY"]))
        else:
            date_imgs.append(None)

    def make_rgba(t):
        canvas  = Image.new("RGBA", (vid_w, vid_h), (0, 0, 0, 0))
        opacity = _fade_opacity(t, dur)

        # Compute each poster's current state
        states = []
        for i in range(n):
            angle = init_angles[i] + rpm * t
            depth  = math.cos(angle)                           # 1=front -1=back
            scale  = min_sc + (max_sc - min_sc) * (depth + 1) / 2
            px     = int(cx + rx * math.sin(angle))
            py     = int(cy + ry * depth)
            states.append((depth, scale, px, py, i))

        # Draw back-to-front (most negative depth first)
        states.sort(key=lambda s: s[0])

        for depth, scale, px, py, i in states:
            img    = imgs[i]
            new_w  = max(1, int(img.width  * scale))
            new_h  = max(1, int(img.height * scale))
            scaled = img.resize((new_w, new_h), Image.LANCZOS)
            _paste_with_alpha(canvas, scaled, px, py, opacity)

            if date_imgs[i] is not None:
                txt = date_imgs[i]
                # Scale date label with poster
                tw  = max(1, int(txt.width  * scale))
                th  = max(1, int(txt.height * scale))
                tsc = txt.resize((tw, th), Image.LANCZOS)
                _paste_with_alpha(canvas, tsc, px, py + new_h // 2 + th // 2 + 4, opacity)

        return np.array(canvas)

    return [_full_frame_clip(make_rgba, dur, vid_w, vid_h, start)]


# ── SPOTLIGHT ─────────────────────────────────────────────────

def style_spotlight(poster_data, grid, vid_w, vid_h):
    """
    Full grid of static posters is always visible.
    A spotlight randomly visits each poster once — the focused poster
    scales up slightly while all others dim.  Each poster gets equal time.
    """
    start     = CFG["START_TIME"]
    dur       = CFG["POSTER_DURATION"]
    n         = len(grid)
    slot_dur  = dur / n
    xfade     = min(CFG["FADE_DURATION"] * 0.5, slot_dur * 0.25)
    SPOT_SCALE= float(os.getenv("SPOTLIGHT_SCALE",  "1.20"))  # focused poster scale
    DIM_LEVEL = float(os.getenv("SPOTLIGHT_DIM",    "0.30"))  # non-focused opacity

    # Random visit order — every poster focused exactly once
    visit_order = list(range(n))
    random.shuffle(visit_order)

    # Pre-render date labels
    date_imgs = []
    for _, (img, date, fx, fy, center_x, bottom_y, phase) in zip(poster_data, grid):
        if CFG["SHOW_RELEASE_DATE"] and date:
            date_imgs.append(make_text_image(
                date, CFG["RELEASE_DATE_SIZE"], CFG["RELEASE_DATE_COLOR"],
                CFG["RELEASE_DATE_SHADOW"], CFG["RELEASE_DATE_BG_COLOR"],
                CFG["RELEASE_DATE_BG_OPACITY"]))
        else:
            date_imgs.append(None)

    print(f"  [spotlight] visit order: {[visit_order[i] for i in range(n)]}  "
          f"slot={slot_dur:.2f}s  scale={SPOT_SCALE}x  dim={DIM_LEVEL}")

    def make_rgba(t):
        canvas  = Image.new("RGBA", (vid_w, vid_h), (0, 0, 0, 0))
        overall = _fade_opacity(t, dur)

        # Which slot are we in and how far through it?
        slot_idx  = min(int(t / slot_dur), n - 1)
        slot_t    = t - slot_idx * slot_dur
        focused_i = visit_order[slot_idx]

        # Crossfade progress for the spotlight (0→1→1→0 within a slot)
        if slot_t < xfade:
            spot_prog = slot_t / xfade
        elif slot_t > slot_dur - xfade:
            spot_prog = max(0.0, (slot_dur - slot_t) / xfade)
        else:
            spot_prog = 1.0

        # ── Pass 1: draw all posters at base opacity ──────────────
        for i, (d, (img, date, fx, fy, center_x, bottom_y, phase)) in                 enumerate(zip(poster_data, grid)):
            if i == focused_i:
                # Focused poster drawn in pass 2
                continue
            # Dim non-focused posters as spotlight comes in
            dim = 1.0 - (1.0 - DIM_LEVEL) * spot_prog
            _paste_with_alpha(canvas, img, fx + img.width // 2,
                              fy + img.height // 2, overall * dim)

            txt = date_imgs[i]
            if txt is not None:
                _paste_with_alpha(canvas, txt, center_x,
                                  bottom_y + 6 + txt.height // 2, overall * dim)

        # ── Pass 2: draw focused poster scaled up on top ──────────
        fimg = poster_data[focused_i]["img"]
        _, (fimg_g, fdate, ffx, ffy, fcx, fby, fphase) =             list(zip(poster_data, grid))[focused_i]

        scale  = 1.0 + (SPOT_SCALE - 1.0) * spot_prog
        new_w  = max(1, int(fimg.width  * scale))
        new_h  = max(1, int(fimg.height * scale))
        scaled = fimg.resize((new_w, new_h), Image.LANCZOS)
        _paste_with_alpha(canvas, scaled,
                          ffx + fimg.width // 2,
                          ffy + fimg.height // 2, overall)

        ftxt = date_imgs[focused_i]
        if ftxt is not None:
            ftw = max(1, int(ftxt.width  * scale))
            fth = max(1, int(ftxt.height * scale))
            fts = ftxt.resize((ftw, fth), Image.LANCZOS)
            _paste_with_alpha(canvas, fts, fcx,
                              fby + 6 + fth // 2 + int((new_h - fimg.height) / 2),
                              overall)

        return np.array(canvas)

    return [_full_frame_clip(make_rgba, dur, vid_w, vid_h, start)]


# ── DISPATCHER ────────────────────────────────────────────────

STYLE_MAP = {
    "bounce":    style_bounce,
    "fade":      style_fade,
    "wave":      style_wave,
    "drift":     style_drift,
    "pop-in":    style_popin,
    "carousel":  style_carousel,
    "spotlight": style_spotlight,
}


def get_style_clips(poster_data, grid, vid_w, vid_h) -> list:
    """Return the list of poster clips for the configured ANIMATION_STYLE."""
    name = CFG.get("ANIMATION_STYLE", "bounce").lower().strip()
    if name not in STYLE_MAP:
        print(f"  ⚠  Unknown ANIMATION_STYLE '{name}' — falling back to 'bounce'")
        name = "bounce"
    print(f"  [style] {name}")
    return STYLE_MAP[name](poster_data, grid, vid_w, vid_h)

# ══════════════════════════════════════════════════════════════
#  VIDEO COMPOSITING
# ══════════════════════════════════════════════════════════════

def composite_video(poster_data: list, bg_path: str, out_path: str):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    bg           = VideoFileClip(str(bg_path))
    vid_w, vid_h = bg.size
    n            = len(poster_data)

    # ── Build grid layout ──────────────────────────────────────
    rows      = build_rows(poster_data)
    n_rows    = len(rows)
    row_max_h = [max(d["img"].height for d in row) for row in rows]
    total_h   = sum(row_max_h) + CFG["ROW_GAP"] * (n_rows - 1)

    block_top = int(vid_h * CFG["VERTICAL_POS"] - total_h / 2)
    block_top = max(10, min(block_top, vid_h - total_h - 10))

    phases = [(2 * math.pi * i) / n for i in range(n)]

    # grid: flat list of (img, date, final_x, final_y, center_x, bottom_y, phase)
    grid      = []
    y_cursor  = block_top
    poster_idx = 0

    for row_num, row in enumerate(rows):
        row_h    = row_max_h[row_num]
        row_w    = sum(d["img"].width for d in row) + CFG["PADDING"] * (len(row) - 1)
        x_cursor = (vid_w - row_w) // 2

        for d in row:
            img    = d["img"]
            phase  = phases[poster_idx]
            poster_idx += 1
            base_y = y_cursor + (row_h - img.height) // 2
            grid.append((
                img,
                d.get("date", ""),
                x_cursor,                    # final_x
                base_y,                      # final_y
                x_cursor + img.width // 2,   # center_x
                base_y + img.height,         # bottom_y
                phase,
            ))
            x_cursor += img.width + CFG["PADDING"]

        y_cursor += row_h + CFG["ROW_GAP"]

    # ── Animation style ───────────────────────────────────────
    all_clips = [bg] + get_style_clips(poster_data, grid, vid_w, vid_h)

    # Bottom message
    if CFG["BOTTOM_MESSAGE_SHOW"] and (CFG["BOTTOM_MESSAGE"] or CFG["BOTTOM_MESSAGE_ADD_DATE"]):
        msg = CFG["BOTTOM_MESSAGE"]
        if CFG["BOTTOM_MESSAGE_ADD_DATE"]:
            now     = datetime.now()
            datestr = f"{now.strftime('%B')} {now.day}, {now.year}"
            msg     = f"{msg}  {datestr}".strip() if msg else datestr
        print(f"  [bottom msg] '{msg}'")
        pos_y = vid_h - 24   # will be adjusted down by image height in clip factory
        # compute actual pos_y after building the image
        img_b = make_text_image(msg,
                    CFG["BOTTOM_MESSAGE_SIZE"], CFG["BOTTOM_MESSAGE_COLOR"],
                    CFG["BOTTOM_MESSAGE_SHADOW"], CFG["BOTTOM_MESSAGE_BG_COLOR"],
                    CFG["BOTTOM_MESSAGE_BG_OPACITY"], max_width=int(vid_w * 0.85))
        pos_x = (vid_w - img_b.width) // 2
        pos_y = vid_h - img_b.height - 24
        all_clips.append(_rgba_to_clip(img_b, pos_x, pos_y,
                                       CFG["START_TIME"], CFG["POSTER_DURATION"]))

    # Top message
    if CFG["TOP_MESSAGE_SHOW"] and (CFG["TOP_MESSAGE"] or CFG["TOP_MESSAGE_ADD_DATE"]):
        msg = CFG["TOP_MESSAGE"]
        if CFG["TOP_MESSAGE_ADD_DATE"]:
            now     = datetime.now()
            datestr = f"{now.strftime('%B')} {now.day}, {now.year}"
            msg     = f"{msg}  {datestr}".strip() if msg else datestr
        print(f"  [top msg] '{msg}'")
        img_t = make_text_image(msg,
                    CFG["TOP_MESSAGE_SIZE"], CFG["TOP_MESSAGE_COLOR"],
                    CFG["TOP_MESSAGE_SHADOW"], CFG["TOP_MESSAGE_BG_COLOR"],
                    CFG["TOP_MESSAGE_BG_OPACITY"], max_width=int(vid_w * 0.85))
        pos_x = (vid_w - img_t.width) // 2
        all_clips.append(_rgba_to_clip(img_t, pos_x, 24,
                                       CFG["START_TIME"], CFG["POSTER_DURATION"]))

    final      = CompositeVideoClip(all_clips).set_duration(bg.duration)
    thread_str = str(CPU_THREADS) if CPU_THREADS > 0 else "0"
    print(f"\n  Rendering → {out_path}  (threads: {thread_str})")
    final.write_videofile(
        str(out_path),
        codec         = "libx264",
        audio_codec   = "aac",
        fps           = bg.fps,
        preset        = VIDEO_PRESET,
        ffmpeg_params = ["-threads", thread_str, "-crf", VIDEO_CRF],
        logger        = None,
    )
    bg.close()
    final.close()



# ══════════════════════════════════════════════════════════════
#  NEXROLL INTEGRATION
# ══════════════════════════════════════════════════════════════

def _nexroll_params(extra: dict = None) -> dict:
    """Build query params with api_key. NeXroll uses ?api_key= not Bearer header."""
    params = {"api_key": NEXROLL_API_KEY}
    if extra:
        params.update(extra)
    return params


def _nexroll_request(method: str, url: str, **kwargs) -> "requests.Response | None":
    """
    Wrapper for NeXroll HTTP calls with retry on transient failures.
    Retries on connection errors and 401s (NeXroll may still be starting up).
    Returns the Response on success, None on permanent failure.
    """
    for attempt in range(1, STARTUP_RETRY_ATTEMPTS + 1):
        try:
            r = requests.request(method, url, **kwargs)

            if r.status_code == 401:
                if attempt < STARTUP_RETRY_ATTEMPTS:
                    print(f"  [nexroll] ⚠  401 on attempt {attempt}/{STARTUP_RETRY_ATTEMPTS} "
                          f"— NeXroll may still be starting, retrying in {STARTUP_RETRY_DELAY}s...")
                    time.sleep(STARTUP_RETRY_DELAY)
                    continue
                print(f"  [nexroll] ❌  Authentication failed (401 Unauthorized)")
                print(f"             Check NEXROLL_API_KEY is correct and has Full Access scope")
                print(f"             NeXroll: Settings → API Keys")
                return None

            if r.status_code == 403:
                print(f"  [nexroll] ❌  Permission denied (403 Forbidden)")
                print(f"             Your API key may be Read-Only — it must be Full Access")
                return None

            if not r.ok:
                body = ""
                try: body = r.text[:300]
                except: pass
                print(f"  [nexroll] ❌  HTTP {r.status_code} from {url}")
                if body:
                    print(f"             Response: {body}")
                return None
            return r

        except requests.exceptions.ConnectionError:
            if attempt < STARTUP_RETRY_ATTEMPTS:
                print(f"  [nexroll] ⚠  Could not connect (attempt {attempt}/{STARTUP_RETRY_ATTEMPTS}), "
                      f"retrying in {STARTUP_RETRY_DELAY}s...")
                time.sleep(STARTUP_RETRY_DELAY)
                continue
            print(f"  [nexroll] ❌  Could not connect to NeXroll at {NEXROLL_URL}")
            print(f"             Is NeXroll running and reachable on the stackarr network?")
            return None

        except requests.exceptions.Timeout:
            print(f"  [nexroll] ❌  NeXroll request timed out ({url})")
            return None

        except requests.RequestException as e:
            print(f"  [nexroll] ❌  Request failed: {e}")
            return None

    return None


def nexroll_get_or_create_category(category_name: str) -> int | None:
    """
    Look up a NeXroll category by name.
    If not found and NEXROLL_CREATE_CATEGORY=True, create it.
    Returns the category_id int, or None on failure.
    """
    base = NEXROLL_URL.rstrip("/")

    r = _nexroll_request("GET", f"{base}/external/categories",
                         params=_nexroll_params(), timeout=10)
    if r is None:
        return None

    data = r.json()
    # Response is {"categories": [...], "count": N}
    cats = data.get("categories", data) if isinstance(data, dict) else data
    for cat in cats:
        if cat.get("name", "").lower() == category_name.lower():
            print(f"  [nexroll] Found category '{category_name}'  id={cat['id']}")
            return cat["id"]

    if not CFG["NEXROLL_CREATE_CATEGORY"]:
        print(f"  [nexroll] ❌  Category '{category_name}' not found and NEXROLL_CREATE_CATEGORY=false")
        return None

    # Create it
    r = _nexroll_request(
        "POST", f"{base}/external/categories",
        params=_nexroll_params(),
        json={"name": category_name},
        timeout=10,
    )
    if r is None:
        return None

    data   = r.json()
    # NeXroll may nest the ID — try common response shapes
    cat_id = (data.get("id")
              or data.get("category_id")
              or (data.get("category") or {}).get("id"))
    print(f"  [nexroll] Created category '{category_name}'  id={cat_id}  response={data}")
    return cat_id


def nexroll_find_existing(host_path: str, base: str) -> dict | None:
    """
    Check if a preroll with this exact path is already registered in NeXroll.
    Returns the preroll dict if found, None otherwise.
    """
    r = _nexroll_request("GET", f"{base}/external/prerolls",
                         params=_nexroll_params(), timeout=10)
    if r is None:
        return None

    data     = r.json()
    prerolls = data.get("prerolls", data) if isinstance(data, dict) else data
    for p in prerolls:
        existing_path = p.get("path") or p.get("file_path") or p.get("full_path", "")
        if existing_path == host_path:
            return p
    return None


def nexroll_register(output_name: str, out_path: Path):
    """
    Register (or skip if already registered) the rendered video with NeXroll.
    Uses CFG for per-job settings. Skips silently if NEXROLL_REGISTER=False
    or if NEXROLL_URL / NEXROLL_API_KEY are not configured.

    NeXroll has no upsert endpoint — we check for an existing entry by path
    first and skip re-registration if found. The video file on disk is always
    updated by the render step regardless.
    """
    if not CFG["NEXROLL_REGISTER"]:
        return

    if not NEXROLL_URL or not NEXROLL_API_KEY:
        print("  [nexroll] ⚠  NEXROLL_URL or NEXROLL_API_KEY not set — skipping registration")
        return

    category_name = CFG["NEXROLL_CATEGORY"].strip()
    if not category_name:
        print("  [nexroll] ⚠  NEXROLL_CATEGORY not set — skipping registration")
        return

    # Translate container output path → NeXroll host path
    if NEXROLL_OUTPUT_PATH:
        host_path = str(NEXROLL_OUTPUT_PATH).rstrip("/") + "/" + out_path.name
    else:
        host_path = str(out_path)

    display_name = CFG["NEXROLL_DISPLAY_NAME"].strip() or output_name
    base         = NEXROLL_URL.rstrip("/")

    print(f"  [nexroll] Registering '{display_name}'")
    print(f"            file_path:    {host_path}")

    # 1 — Check if already registered (avoid duplicates on repeat runs)
    existing = nexroll_find_existing(host_path, base)
    if existing:
        print(f"  [nexroll] ✅  Already registered  id={existing.get('id')}  — skipping"
              f" (file on disk updated, NeXroll entry unchanged)")
        return

    # 2 — Look up / create category
    cat_id = nexroll_get_or_create_category(category_name)
    if cat_id is None:
        return

    print(f"            category_id:  {cat_id}")

    # 3 — Register the preroll
    payload = {
        "path":         host_path,
        "display_name": display_name,
        "category_id":  cat_id,
    }
    r = _nexroll_request(
        "POST", f"{base}/external/prerolls/register",
        params=_nexroll_params(),
        json=payload,
        timeout=15,
    )
    if r is None:
        return

    preroll = r.json()
    print(f"  [nexroll] ✅  Registered  id={preroll.get('id')}  category='{category_name}'")

    # 4 — Optionally apply category to Plex immediately
    if CFG["NEXROLL_APPLY_TO_PLEX"]:
        r = _nexroll_request(
            "POST", f"{base}/external/apply-category/{cat_id}",
            params=_nexroll_params(),
            timeout=10,
        )
        if r is not None:
            print(f"  [nexroll] ✅  Category '{category_name}' applied to Plex")


# ══════════════════════════════════════════════════════════════
#  JOB RUNNER
# ══════════════════════════════════════════════════════════════

def run_job(video_path: Path, yaml_path: Path):
    print(f"\n{'═' * 54}")
    print(f"  Job: {yaml_path.name}")

    source_type, output_name, yaml_settings = parse_yaml(yaml_path)
    load_job_config(yaml_settings)

    out_path  = Path(OUTPUT_DIR) / f"{output_name}.mp4"
    n         = max(1, min(CFG["NUM_POSTERS"], 10))
    rows_prev = build_rows([None] * n)
    layout    = " + ".join(str(len(r)) for r in rows_prev)

    print(f"  Source:    {video_path.name}")
    print(f"  Type:      {source_type.upper()}")
    print(f"  Output:    {out_path.name}")
    print(f"  Posters:   {n}  layout={layout}  start={CFG['START_TIME']}s  show={CFG['POSTER_DURATION']}s")
    print(f"  Font:      {CFG['FONT']}")

    # Animation style + relevant parameters
    style = CFG.get("ANIMATION_STYLE", "bounce").lower().strip()
    style_params = {
        "bounce":    f"amplitude={CFG['FLOAT_AMPLITUDE']}  speed={CFG['FLOAT_SPEED']}",
        "fade":      "",
        "wave":      f"stagger={os.getenv('WAVE_STAGGER', '0.3')}s",
        "pop-in":    f"scale={os.getenv('POPIN_SCALE','2.5')}x  duration={os.getenv('POPIN_DURATION','1.0')}s  stagger={os.getenv('POPIN_STAGGER','0.3')}s",
        "carousel":  f"rx={os.getenv('CAROUSEL_RX','0.32')}  ry={os.getenv('CAROUSEL_RY','0.06')}  scale={os.getenv('CAROUSEL_MIN_SCALE','0.45')}–{os.getenv('CAROUSEL_MAX_SCALE','1.0')}",
        "spotlight": f"size={os.getenv('SPOTLIGHT_SIZE','0.35')}  breathe={os.getenv('SPOTLIGHT_BREATHE','0.03')}",
        "drift":     f"speed={os.getenv('DRIFT_SPEED','30')}px/s  dir={os.getenv('DRIFT_DIRECTION','left')}",
    }
    params_str = style_params.get(style, "")
    print(f"  Style:     {style}" + (f"  ({params_str})" if params_str else ""))
    print(f"  Date: {'on' if CFG['SHOW_RELEASE_DATE'] else 'off'}"
          f"   Bottom: {'on' if CFG['BOTTOM_MESSAGE_SHOW'] else 'off'}"
          f"   Top: {'on' if CFG['TOP_MESSAGE_SHOW'] else 'off'}")
    print(f"{'─' * 54}")

    # Fetch entries
    print(f"\n  Fetching {n} upcoming {'movies' if source_type == 'movie' else 'TV shows'}...")
    entries = get_upcoming_movies(n) if source_type == "movie" else get_upcoming_tv(n)

    if not entries:
        print(f"  No upcoming entries found — skipping {output_name}")
        return

    print(f"  Selected {len(entries)}:")
    for e in entries:
        rd = e["release"]
        print(f"    • {e['title']}  ({rd.strftime('%B')} {rd.day}, {rd.year})")

    # Download and prepare posters
    poster_data = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, e in enumerate(entries):
            path = os.path.join(tmpdir, f"poster_{i}.jpg")
            print(f"  ↓  {e['title']}")
            if download_poster(e, path, source_type):
                rd       = e["release"]
                date_str = (f"{rd.strftime('%B')} {rd.day}, {rd.year}"
                            if CFG["SHOW_RELEASE_DATE"] else "")
                poster_data.append({
                    "img":  prepare_poster(path),
                    "date": date_str,
                })
            else:
                print(f"     (skipped — poster unavailable)")

        if not poster_data:
            print(f"  No posters downloaded — skipping {output_name}")
            return

        composite_video(poster_data, video_path, out_path)

    print(f"\n  ✅  {output_name}.mp4  saved to {OUTPUT_DIR}")
    nexroll_register(output_name, out_path)


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print("═" * 54)
    print(f"  floating-posters  v{VERSION}")
    print(f"  Input dir:   {INPUT_DIR}")
    print(f"  Output dir:  {OUTPUT_DIR}")
    print(f"  Radarr:      {RADARR_URL}")
    print(f"  Sonarr:      {SONARR_URL}")
    print(f"  Threads:     {CPU_THREADS}   CRF: {VIDEO_CRF}   Preset: {VIDEO_PRESET}")
    print(f"  Retry:       {STARTUP_RETRY_ATTEMPTS} attempts  delay: {STARTUP_RETRY_DELAY}s")
    if NEXROLL_URL:
        print(f"  NeXroll:     {NEXROLL_URL}")
    print("═" * 54)

    # Ensure output dir exists
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    jobs = find_jobs(INPUT_DIR)
    if not jobs:
        print(f"\nNo video+yaml pairs found in {INPUT_DIR}")
        print("  Expected: <name>.mov (or .mp4/.mpg) + <name>.yaml side by side")
        sys.exit(1)

    print(f"\nFound {len(jobs)} job(s):")
    for v, y in jobs:
        print(f"  {v.name}  +  {y.name}")

    for video_path, yaml_path in jobs:
        try:
            run_job(video_path, yaml_path)
        except Exception as e:
            print(f"\n  ❌  {yaml_path.name} failed: {e}")
            import traceback
            traceback.print_exc()
            print("  Continuing with next job...\n")

    print(f"\n{'═' * 54}")
    print(f"  All jobs complete.")
    print(f"{'═' * 54}")


if __name__ == "__main__":
    main()
