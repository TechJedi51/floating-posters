# 🎬 floating-posters  `v1.3.0`

A Docker container that fetches upcoming movie posters from **Radarr** and composites them as **floating, animated overlays** onto a background video — ready to drop into [NeXroll](https://github.com/JFLXCLOUD/NeXroll) as a Plex preroll.

![GitHub Actions](https://github.com/TechJedi51/floating-posters/actions/workflows/docker-build.yml/badge.svg)

---

## How it works

1. Queries your Radarr library for upcoming releases (sorted by nearest release date)
2. Downloads poster art for the selected movies
3. Composites 1–6 posters as floating overlays on your background video
4. Each poster group fades in, floats gently (staggered sine-wave motion), and fades out
5. Optionally renders the release date beneath each poster
6. Saves the finished video to your output directory

---

## Quick start

### 1. Pull the image

```bash
docker pull ghcr.io/TechJedi51/floating-posters:latest
```

### 2. Run it

```bash
docker run --rm \
  -v /path/to/background.mp4:/input/background.mp4:ro \
  -v /path/to/output:/output \
  -e RADARR_URL=http://your-radarr:7878 \
  -e RADARR_API_KEY=your_api_key \
  ghcr.io/TechJedi51/floating-posters:latest
```

The finished video will be at `/path/to/output/output.mp4`.

---

## docker-compose

Copy `docker-compose.yml` and edit the `volumes` and `environment` sections:

```yaml
services:
  floating-posters:
    image: ghcr.io/TechJedi51/floating-posters:latest
    volumes:
      - /mnt/media/prerolls/background.mp4:/input/background.mp4:ro
      - /mnt/media/prerolls/output:/output
    environment:
      - RADARR_URL=http://192.168.1.100:7878
      - RADARR_API_KEY=abc123yourkeyhere
      - NUM_POSTERS=5
      - START_TIME=3.0
      - POSTER_DURATION=9.0
      - SHOW_RELEASE_DATE=true
      - RELEASE_DATE_COLOR=#FFFFFF
    restart: "no"
```

Then run:

```bash
docker compose run --rm floating-posters
```

---

## Configuration

All settings are environment variables. See [`.env.example`](.env.example) for the full list with descriptions.

### Radarr connection

| Variable | Default | Description |
|---|---|---|
| `RADARR_URL` | `http://localhost:7878` | Radarr base URL |
| `RADARR_API_KEY` | *(required)* | Radarr → Settings → General → API Key |

### File paths

| Variable | Default | Description |
|---|---|---|
| `INPUT_VIDEO` | `/input/background.mp4` | Background video path inside container |
| `OUTPUT_VIDEO` | `/output/output.mp4` | Output path inside container |

### Timing

| Variable | Default | Description |
|---|---|---|
| `START_TIME` | `2.0` | Seconds into video where posters first appear |
| `POSTER_DURATION` | `8.0` | How long posters are visible (max `10.0`) |
| `FADE_DURATION` | `0.75` | Fade in/out duration in seconds |

### Poster selection

| Variable | Default | Description |
|---|---|---|
| `NUM_POSTERS` | `4` | Number of posters to overlay (1–6) |
| `UPCOMING_DAYS` | `180` | Days ahead to scan for upcoming releases |

### Poster appearance

| Variable | Default | Description |
|---|---|---|
| `POSTER_WIDTH` | `185` | Poster width in pixels (height auto-scales) |
| `PADDING` | `28` | Pixels between posters |
| `VERTICAL_POS` | `0.52` | Row position: `0.0`=top · `0.5`=center · `1.0`=bottom |
| `CORNER_RADIUS` | `10` | Rounded corner radius in pixels |

### Drop shadow

| Variable | Default | Description |
|---|---|---|
| `ADD_SHADOW` | `true` | Drop shadow behind posters |
| `SHADOW_OFFSET_X` | `7` | Horizontal shadow offset in pixels |
| `SHADOW_OFFSET_Y` | `9` | Vertical shadow offset in pixels |
| `SHADOW_BLUR` | `9` | Shadow softness (Gaussian blur radius) |
| `SHADOW_OPACITY` | `175` | Shadow darkness: `0`=invisible · `255`=solid black |

### Release date label *(new in v1.1.0)*

| Variable | Default | Description |
|---|---|---|
| `SHOW_RELEASE_DATE` | `true` | Show release date below each poster |
| `RELEASE_DATE_COLOR` | `#FFFFFF` | Text color — hex (`#FF6B6B`) or CSS name (`white`, `gold`) |
| `RELEASE_DATE_SIZE` | `15` | Font size in pixels |
| `RELEASE_DATE_SHADOW` | `true` | Drop shadow behind the date text |

### CPU throttle *(new in v1.2.0)*

| Variable | Default | Description |
|---|---|---|
| `CPU_THREADS` | `2` | FFmpeg thread limit. `0` = unlimited (uses all cores) |

> Also set `deploy.resources.limits.cpus` in `docker-compose.yml` to cap the container itself.

### Bottom message *(new in v1.3.0)*

| Variable | Default | Description |
|---|---|---|
| `BOTTOM_MESSAGE_SHOW` | `false` | Enable the bottom message overlay |
| `BOTTOM_MESSAGE` | *(empty)* | Text to display at the bottom of the screen |
| `BOTTOM_MESSAGE_ADD_DATE` | `true` | Append today's date — e.g. `Updated  April 20, 2026` |
| `BOTTOM_MESSAGE_COLOR` | `white` | Hex (`#RRGGBB`) or CSS color name |
| `BOTTOM_MESSAGE_SIZE` | `15` | Font size in pixels |

### Float animation

| Variable | Default | Description |
|---|---|---|
| `FLOAT_AMPLITUDE` | `14.0` | Max pixels of vertical drift (sine wave) |
| `FLOAT_SPEED` | `0.55` | Oscillations per second — lower = slower, dreamier |

### Output encoding

| Variable | Default | Description |
|---|---|---|
| `VIDEO_CRF` | `18` | FFmpeg CRF: `18`=near-lossless · `23`=default · `28`=smaller file |
| `VIDEO_PRESET` | `fast` | FFmpeg preset: `ultrafast`/`fast`/`medium`/`slow` |

---

## Scheduling with cron

To regenerate the preroll nightly and keep it fresh:

```cron
# Regenerate Plex upcoming preroll every night at 2 AM
0 2 * * * docker compose -f /path/to/floating-posters/docker-compose.yml run --rm floating-posters
```

Then point NeXroll at the output file as a scheduled preroll.

---

## Building locally

```bash
git clone https://github.com/TechJedi51/floating-posters
cd floating-posters
docker build -t floating-posters .
docker run --rm \
  -v /path/to/background.mp4:/input/background.mp4:ro \
  -v /path/to/output:/output \
  -e RADARR_URL=http://your-radarr:7878 \
  -e RADARR_API_KEY=your_key \
  floating-posters
```

---

## GitHub Actions

On every push to `main`, GitHub Actions automatically:
- Builds for `linux/amd64` and `linux/arm64` (Apple Silicon / Unraid)
- Pushes `ghcr.io/TechJedi51/floating-posters:latest`
- Tags version releases (`v1.3.0`) as `:1.3.0` and `:1.3`

The `GITHUB_TOKEN` is used automatically — no secrets to configure.

---

## Requirements (if running without Docker)

```bash
pip install moviepy pillow requests numpy
brew install ffmpeg   # macOS
```

---

## Changelog

### v1.3.0
- **Fixed release date not showing** — root cause was a broken indentation in the previous string replacement that put `poster_images.append()` inside the wrong branch; text rendering architecture completely reworked
- Text labels (date, bottom message) are now **separate clips** in the composite instead of being embedded in the poster RGBA image — sidesteps the alpha pipeline entirely and is guaranteed to work
- **Date format** changed to `April 20, 2026` style (no platform-specific strftime modifiers)
- **Date labels float in sync with their poster** (same sine-wave phase)
- Added `BOTTOM_MESSAGE` overlay — centered at the bottom of the screen, fades with the poster group; optionally appends today's date

### v1.2.0
- **Security**: upgraded to Python 3.13, added `apt-get upgrade` for patched openssl/libssl
- **CPU limiting**: added `CPU_THREADS` env var (`-threads N` passed to FFmpeg); pair with `deploy.resources.limits.cpus` in docker-compose for a full container cap
- **Release date fix**: replaced Linux-only `%-m/%-d` strftime modifiers with explicit date formatting; added semi-transparent dark pill background behind label text so it's readable against any video background; improved font fallback for Pillow 10+

### v1.1.0
- Added release date label below each poster (`SHOW_RELEASE_DATE`, `RELEASE_DATE_COLOR`, `RELEASE_DATE_SIZE`, `RELEASE_DATE_SHADOW`)
- Fixed `set_opacity` TypeError with moviepy 1.0.3 — replaced with `VideoClip` mask for proper per-frame fade with alpha preservation
- Poster alpha channel (rounded corners, drop shadow) now correctly composited through the fade animation

### v1.0.0
- Initial release
- Radarr API integration for upcoming movie poster fetching
- Floating sine-wave animation with staggered phase per poster
- Configurable fade in/out, drop shadow, rounded corners
- Multi-arch Docker image (amd64 + arm64)
- Full environment variable configuration

---

## Credits

Built to work with [NeXroll](https://github.com/JFLXCLOUD/NeXroll) by JFLXCLOUD.  
Poster art sourced from your Radarr library via the Radarr v3 API.
