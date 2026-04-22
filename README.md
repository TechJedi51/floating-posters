# 🎬 floating-posters  `v1.7.0`

A Docker container that fetches upcoming movie and TV posters from **Radarr** and **Sonarr**, and composites them as **floating, animated overlays** onto background videos — ready to drop into [NeXroll](https://github.com/JFLXCLOUD/NeXroll) as Plex prerolls.

![GitHub Actions](https://github.com/TechJedi51/floating-posters/actions/workflows/docker-build.yml/badge.svg)

---

## How it works

1. Scans `/input` for video files (`.mov`, `.mp4`, `.m4v`, `.mpg`, `.mkv`)
2. Each video must have a matching `.yaml` file with the same name
3. The yaml top-level key determines the poster source:
   - `movie:` → fetches posters from **Radarr**
   - `tv:` → fetches posters from **Sonarr**
4. Each video is processed independently using its yaml settings
5. Output files are saved to `/output` named by the `output=` field in the yaml

---

## Source folder layout

```
/input/
  RedCurtainsv2.mov       ← background video
  RedCurtainsv2.yaml      ← matching config (must be same name)
  TheaterSmokev1.mov
  TheaterSmokev1.yaml
```

```
/output/
  RedCurtains.mp4         ← named by output= in the yaml
  TheaterSmokev1.mp4
```

---

## Quick start

### 1. Pull the image

```bash
docker pull ghcr.io/TechJedi51/floating-posters:latest
```

### 2. docker-compose.yml

```yaml
services:
  floating-posters:
    image: ghcr.io/TechJedi51/floating-posters:latest
    volumes:
      - /path/to/source:/input
      - /path/to/output:/output
    environment:
      - RADARR_URL=http://192.168.1.100:7878
      - RADARR_API_KEY=${RADARR_API_KEY}
      - SONARR_URL=http://192.168.1.100:8989
      - SONARR_API_KEY=${SONARR_API_KEY}
      - CPU_THREADS=2
      - VIDEO_CRF=18
      - VIDEO_PRESET=fast
    restart: "no"
    deploy:
      resources:
        limits:
          cpus: "2.0"
```

### 3. Run it

```bash
docker compose run --rm floating-posters
```

---

## docker-compose environment

Only global / connection settings go here. All per-video settings go in the yaml.

| Variable | Default | Description |
|---|---|---|
| `RADARR_URL` | `http://localhost:7878` | Radarr base URL |
| `RADARR_API_KEY` | *(required)* | Radarr → Settings → General → API Key |
| `SONARR_URL` | `http://localhost:8989` | Sonarr base URL (required for `tv:` yamls) |
| `SONARR_API_KEY` | *(optional)* | Sonarr API Key |
| `CPU_THREADS` | `2` | FFmpeg thread limit (`0` = unlimited) |
| `VIDEO_CRF` | `18` | `18`=near-lossless · `23`=default · `28`=smaller |
| `VIDEO_PRESET` | `fast` | `ultrafast`/`fast`/`medium`/`slow` |

---

## yaml format

See `.yaml.example` for a fully annotated template. The structure is:

```yaml
movie:               # or tv: for Sonarr
  - output=MyPreroll
  - FONT=Poppins-Bold
  - NUM_POSTERS=10
  - START_TIME=3.0
  - TOP_MESSAGE_SHOW=true
  - TOP_MESSAGE=Coming Soon to SEAL iPlex
  - TOP_MESSAGE_SIZE=90
  - TOP_MESSAGE_BG_OPACITY=0
  - BOTTOM_MESSAGE_SHOW=true
  - BOTTOM_MESSAGE=Updated
  - BOTTOM_MESSAGE_ADD_DATE=true
  ...
```

### Font

| Setting | Default | Options |
|---|---|---|
| `FONT` | `Poppins-Bold` | See full list below |

**Available fonts:**
`Poppins-Bold` · `Poppins-Medium` · `Poppins-Regular` · `DejaVuSans-Bold` · `DejaVuSans` · `DejaVuSerif-Bold` · `DejaVuSerif` · `DejaVuSansMono-Bold` · `DejaVuSansCondensed-Bold` · `LiberationSans-Bold` · `LiberationSans` · `LiberationSerif-Bold` · `LiberationMono-Bold` · `FreeSansBold` · `FreeSerifBold` · `Carlito-Bold` · `Caladea-Bold`

### Poster selection

| Setting | Default | Description |
|---|---|---|
| `NUM_POSTERS` | `4` | 1–10. 6+ triggers automatic 2-row layout. |
| `UPCOMING_DAYS` | `180` | Days ahead to scan for upcoming releases |

**2-row layout:** 6 (3+3) · 7 (4+3) · 8 (4+4) · 9 (5+4) · 10 (5+5). Each row is independently centred.

### Timing

| Setting | Default | Description |
|---|---|---|
| `START_TIME` | `2.0` | Seconds into video where posters appear |
| `POSTER_DURATION` | `8.0` | How long posters are visible (max 10s) |
| `FADE_DURATION` | `0.75` | Fade in/out duration |

### Poster appearance

| Setting | Default | Description |
|---|---|---|
| `POSTER_WIDTH` | `185` | Width in pixels (height auto-scales) |
| `PADDING` | `28` | Pixels between posters |
| `ROW_GAP` | `24` | Pixels between rows (2-row layout) |
| `VERTICAL_POS` | `0.52` | `0.0`=top · `0.5`=center · `1.0`=bottom |
| `CORNER_RADIUS` | `10` | Rounded corner radius |

### Drop shadow

| Setting | Default | Description |
|---|---|---|
| `ADD_SHADOW` | `true` | Poster drop shadow |
| `SHADOW_OFFSET_X` | `7` | Horizontal offset |
| `SHADOW_OFFSET_Y` | `9` | Vertical offset |
| `SHADOW_BLUR` | `9` | Softness (Gaussian blur radius) |
| `SHADOW_OPACITY` | `175` | `0`=invisible · `255`=solid |

### Release date label

| Setting | Default | Description |
|---|---|---|
| `SHOW_RELEASE_DATE` | `true` | Show date below each poster |
| `RELEASE_DATE_COLOR` | `#FFFFFF` | Text color |
| `RELEASE_DATE_SIZE` | `15` | Font size in pixels |
| `RELEASE_DATE_SHADOW` | `true` | Drop shadow behind text |
| `RELEASE_DATE_BG_COLOR` | `#000000` | Pill background color |
| `RELEASE_DATE_BG_OPACITY` | `170` | `0`=none · `170`=semi · `255`=solid |

### Top message

| Setting | Default | Description |
|---|---|---|
| `TOP_MESSAGE_SHOW` | `false` | Enable top message |
| `TOP_MESSAGE` | *(empty)* | Text to display |
| `TOP_MESSAGE_ADD_DATE` | `false` | Append today's date |
| `TOP_MESSAGE_COLOR` | `white` | Text color |
| `TOP_MESSAGE_SIZE` | `15` | Font size in pixels |
| `TOP_MESSAGE_SHADOW` | `false` | Drop shadow |
| `TOP_MESSAGE_BG_COLOR` | `#000000` | Pill background |
| `TOP_MESSAGE_BG_OPACITY` | `170` | `0`=none · `255`=solid |

### Bottom message

| Setting | Default | Description |
|---|---|---|
| `BOTTOM_MESSAGE_SHOW` | `false` | Enable bottom message |
| `BOTTOM_MESSAGE` | *(empty)* | Text to display |
| `BOTTOM_MESSAGE_ADD_DATE` | `true` | Append today's date |
| `BOTTOM_MESSAGE_COLOR` | `white` | Text color |
| `BOTTOM_MESSAGE_SIZE` | `15` | Font size in pixels |
| `BOTTOM_MESSAGE_SHADOW` | `false` | Drop shadow |
| `BOTTOM_MESSAGE_BG_COLOR` | `#000000` | Pill background |
| `BOTTOM_MESSAGE_BG_OPACITY` | `170` | `0`=none · `255`=solid |

### Float animation

| Setting | Default | Description |
|---|---|---|
| `FLOAT_AMPLITUDE` | `14.0` | Max pixels of vertical drift |
| `FLOAT_SPEED` | `0.55` | Oscillations per second |

---

## Scheduling with cron

```cron
# Regenerate prerolls every night at 2 AM
0 2 * * * docker compose -f /path/to/floating-posters/docker-compose.yml run --rm floating-posters
```

---

## Building locally

```bash
git clone https://github.com/TechJedi51/floating-posters
cd floating-posters
docker build -t floating-posters .
docker run --rm \
  -v /path/to/source:/input \
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
- Tags version releases (`v1.7.0`) as `:1.7.0` and `:1.7`

---

## Changelog

### v1.7.0
- **New architecture**: scan-based multi-video processing — one run processes all video+yaml pairs in `/input`
- **yaml-driven config**: all per-video settings move from docker-compose env vars to individual `.yaml` files
- **Sonarr support**: `tv:` yaml key fetches upcoming TV series posters via Sonarr calendar API
- **docker-compose simplified**: only connection/quality env vars remain; everything else is per-yaml
- `pyyaml` added to dependencies

### v1.6.0
- Text wrapping for top/bottom messages (word-wraps at 85% of video width)
- Multi-row poster layout: 6–10 posters split into 2 rows, each row centred independently
- `ROW_GAP` config; `NUM_POSTERS` max raised to 10

### v1.5.0
- `*_BG_COLOR` and `*_BG_OPACITY` for all three text areas; `BG_OPACITY=0` removes pill

### v1.4.0
- `FONT` option with 17 bundled fonts; Poppins-Bold default
- `TOP_MESSAGE` overlay; `BOTTOM_MESSAGE_SHADOW`

### v1.3.0
- Release date labels as separate clips (float in sync with poster)
- Bottom message overlay; date format `April 20, 2026`

### v1.2.0
- Python 3.13; `apt-get upgrade` for patched openssl/libssl; `CPU_THREADS`

### v1.1.0
- `SHOW_RELEASE_DATE`, `RELEASE_DATE_COLOR/SIZE/SHADOW`
- Fixed `set_opacity` TypeError with moviepy 1.0.3

### v1.0.0
- Initial release

---

## Credits

Built to work with [NeXroll](https://github.com/JFLXCLOUD/NeXroll) by JFLXCLOUD.  
Poster art sourced from Radarr and Sonarr via their v3 APIs.
