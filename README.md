# 🎬 floating-posters

A Docker container that fetches upcoming movie posters from **Radarr** and composites them as **floating, animated overlays** onto a background video — ready to drop into [NeXroll](https://github.com/JFLXCLOUD/NeXroll) as a Plex preroll.

![GitHub Actions](https://github.com/YOUR_GITHUB_USERNAME/floating-posters/actions/workflows/docker-build.yml/badge.svg)

---

## How it works

1. Queries your Radarr library for upcoming releases (sorted by nearest release date)
2. Downloads poster art for the selected movies
3. Composites 1–6 posters as floating overlays on your background video
4. Each poster group fades in, floats gently (staggered sine-wave motion), and fades out
5. Saves the finished video to your output directory

---

## Quick start

### 1. Pull the image

```bash
docker pull ghcr.io/YOUR_GITHUB_USERNAME/floating-posters:latest
```

### 2. Run it

```bash
docker run --rm \
  -v /path/to/background.mp4:/input/background.mp4:ro \
  -v /path/to/output:/output \
  -e RADARR_URL=http://your-radarr:7878 \
  -e RADARR_API_KEY=your_api_key \
  ghcr.io/YOUR_GITHUB_USERNAME/floating-posters:latest
```

The finished video will be at `/path/to/output/output.mp4`.

---

## docker-compose

Copy `docker-compose.yml` and edit the `volumes` and `environment` sections:

```yaml
services:
  floating-posters:
    image: ghcr.io/YOUR_GITHUB_USERNAME/floating-posters:latest
    volumes:
      - /mnt/media/prerolls/background.mp4:/input/background.mp4:ro
      - /mnt/media/prerolls/output:/output
    environment:
      - RADARR_URL=http://192.168.1.100:7878
      - RADARR_API_KEY=abc123yourkeyhere
      - NUM_POSTERS=5
      - START_TIME=3.0
      - POSTER_DURATION=9.0
    restart: "no"
```

Then run:

```bash
docker compose run --rm floating-posters
```

---

## Configuration

All settings are environment variables. See [`.env.example`](.env.example) for the full list with descriptions.

| Variable | Default | Description |
|---|---|---|
| `RADARR_URL` | `http://localhost:7878` | Radarr base URL |
| `RADARR_API_KEY` | *(required)* | Radarr → Settings → General → API Key |
| `INPUT_VIDEO` | `/input/background.mp4` | Background video path inside container |
| `OUTPUT_VIDEO` | `/output/output.mp4` | Output path inside container |
| `START_TIME` | `2.0` | Seconds into video where posters first appear |
| `POSTER_DURATION` | `8.0` | How long posters are visible (max `10.0`) |
| `FADE_DURATION` | `0.75` | Fade in/out seconds |
| `NUM_POSTERS` | `4` | Number of posters to overlay (1–6) |
| `UPCOMING_DAYS` | `180` | Days ahead to scan for upcoming releases |
| `POSTER_WIDTH` | `185` | Poster width in pixels (height auto-scales) |
| `PADDING` | `28` | Pixels between posters |
| `VERTICAL_POS` | `0.52` | Row position: `0.0`=top · `0.5`=center · `1.0`=bottom |
| `FLOAT_AMPLITUDE` | `14.0` | Pixels of vertical drift (sine wave) |
| `FLOAT_SPEED` | `0.55` | Oscillations per second (lower = dreamier) |
| `ADD_SHADOW` | `true` | Drop shadow behind posters |
| `VIDEO_CRF` | `18` | FFmpeg CRF: `18`=near-lossless · `23`=default · `28`=smaller |
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
git clone https://github.com/YOUR_GITHUB_USERNAME/floating-posters
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
- Pushes `ghcr.io/YOUR_GITHUB_USERNAME/floating-posters:latest`
- Tags version releases (`v1.0.0`) as `:1.0.0` and `:1.0`

The `GITHUB_TOKEN` is used automatically — no secrets to configure.

---

## Requirements (if running without Docker)

```bash
pip install moviepy pillow requests numpy
brew install ffmpeg   # macOS
```

---

## Credits

Built to work with [NeXroll](https://github.com/JFLXCLOUD/NeXroll) by JFLXCLOUD.  
Poster art sourced from your Radarr library via the Radarr v3 API.
