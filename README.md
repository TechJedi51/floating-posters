# 🎬 floating-posters  `v1.9.9`

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
5. Output files are saved to `/output` (or `OUTPUT_DIR` if set) named by the `output=` field in the yaml

## Sample Videos to use:
> [!NOTE]
> (Use them with the SampleTV.yaml and SampleMovie.yaml files)

### 📺 TV Sample
▶️ [Watch on YouTube](https://youtu.be/Hjvc9LJRTt4)

### 🎬 Movie Sample
▶️ [Watch on YouTube](https://youtu.be/0LrKlTkHwA4)

---

## Sample Videos to use:
> [!NOTE]
> (Use them with the SampleTV.yaml and SampleMovie.yaml files)
### 📺 TV Sample
▶️ [Watch on YouTube](https://youtu.be/Hjvc9LJRTt4)
### 🎬 Movie Sample
▶️ [Watch on YouTube](https://youtu.be/0LrKlTkHwA4)
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
      - /path/to/output:/output   # see Output section below for NeXroll shared volume alternative
    environment:
      - RADARR_URL=http://192.168.1.100:7878
      - RADARR_API_KEY=${RADARR_API_KEY}
      - SONARR_URL=http://192.168.1.100:8989
      - SONARR_API_KEY=${SONARR_API_KEY}
      - NEXROLL_URL=http://192.168.1.100:9393   # optional
      - NEXROLL_API_KEY=${NEXROLL_API_KEY}
      - NEXROLL_OUTPUT_PATH=/path/to/output     # optional — see Output section
      - RERUN_INTERVAL=24h
      - CPU_THREADS=2
      - VIDEO_CRF=18
      - VIDEO_PRESET=fast
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "2.0"
```

> **Tip:** If floating-posters is in the same stack as Radarr, Sonarr, and NeXroll, add them all to `depends_on` to ensure container start order. The `STARTUP_RETRY_ATTEMPTS` and `STARTUP_RETRY_DELAY` env vars handle the gap between a container starting and the service being ready to accept API calls.

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
| `NEXROLL_URL` | *(optional)* | NeXroll base URL — enables registration if set |
| `NEXROLL_API_KEY` | *(optional)* | NeXroll full-access API key (Settings → API Keys) |
| `NEXROLL_OUTPUT_PATH` | *(optional)* | Host path NeXroll sees for your output folder |
| `STARTUP_RETRY_ATTEMPTS` | `5` | Times to retry connecting to Radarr/Sonarr before giving up |
| `STARTUP_RETRY_DELAY` | `30` | Seconds between retry attempts |
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

### NeXroll registration

After each successful render, floating-posters can automatically register the output with NeXroll — creating the category if needed and optionally applying it to Plex immediately.

Requires `NEXROLL_URL`, `NEXROLL_API_KEY`, and `NEXROLL_OUTPUT_PATH` in docker-compose. The API key must be **full access** (Settings → API Keys in NeXroll).

| Setting | Default | Description |
|---|---|---|
| `NEXROLL_REGISTER` | `false` | Enable registration after render |
| `NEXROLL_CATEGORY` | *(empty)* | NeXroll category name to register under |
| `NEXROLL_DISPLAY_NAME` | *(empty)* | Display name in NeXroll (defaults to `output=` value) |
| `NEXROLL_CREATE_CATEGORY` | `true` | Create the category in NeXroll if it doesn't exist |
| `NEXROLL_APPLY_TO_PLEX` | `false` | Immediately apply the category to Plex after registering |

---

## Output configuration

### Standalone (no NeXroll)

Map any host folder to `/output`. Videos are written there directly.

```yaml
volumes:
  - /path/to/output:/output
```

`OUTPUT_DIR` defaults to `/output` and does not need to be set unless you want to write into a subfolder of the mounted volume.

### Integrated with NeXroll (shared Docker volume)

When floating-posters and NeXroll run in the same stack, mount the same named volume that NeXroll uses and set `OUTPUT_DIR` to point at NeXroll's preroll subfolder. Set `NEXROLL_OUTPUT_PATH` to the same path so NeXroll can locate the files when registering them.

```yaml
  floating-posters:
    volumes:
      - /path/to/source:/input
      - type: volume
        source: plexserver_nexroll      # same volume NeXroll uses
        target: /nexroll_media
        volume:
          nocopy: true
    environment:
      - OUTPUT_DIR=/nexroll_media/Pre-Rolls
      - NEXROLL_OUTPUT_PATH=/nexroll_media/Pre-Rolls
      - NEXROLL_URL=http://nexroll:9393
      - NEXROLL_API_KEY=${NEXROLL_API_KEY}
```

With this setup there is no need for `NEXROLL_OUTPUT_PATH` to translate between host and container paths — both containers share the same volume and see the same path.

**`NEXROLL_OUTPUT_PATH` in standalone mode:** If floating-posters and NeXroll are in separate stacks (not sharing a volume), `NEXROLL_OUTPUT_PATH` must be set to the host filesystem path that NeXroll can access. For example if your volume is `- /mnt/media/prerolls:/output`, set `NEXROLL_OUTPUT_PATH=/mnt/media/prerolls`.

### Float animation

| Setting | Default | Description |
|---|---|---|
| `FLOAT_AMPLITUDE` | `14.0` | Max pixels of vertical drift |
| `FLOAT_SPEED` | `0.55` | Oscillations per second |

---

## Startup retry

When floating-posters starts at the same time as Radarr/Sonarr (e.g. on a fresh stack deploy or reboot), the *arr services may not be ready to accept API calls immediately even after their containers are running. The retry settings handle this gracefully:

| Variable | Default | Description |
|---|---|---|
| `STARTUP_RETRY_ATTEMPTS` | `5` | Number of connection attempts before giving up |
| `STARTUP_RETRY_DELAY` | `30` | Seconds to wait between attempts |

With defaults, floating-posters will wait up to **2.5 minutes** for Radarr/Sonarr to become available before failing. Each attempt is logged:

```
  ⚠  Radarr not ready (attempt 1/5): Connection refused
     Retrying in 30s...
  ⚠  Radarr not ready (attempt 2/5): Connection refused
     Retrying in 30s...
  [font] Poppins-Bold  size=15
  ...
```

If you're running floating-posters in the same docker-compose stack as Radarr and Sonarr, also add `depends_on` to ensure container start order:

```yaml
depends_on:
  - radarr
  - sonarr
  - nexroll
```

> **Note:** `depends_on` only guarantees that the Radarr/Sonarr *containers* start before floating-posters — not that the services inside them are ready. The retry logic handles the remaining gap.

## Scheduling

Set `RERUN_INTERVAL` in docker-compose and change `restart: unless-stopped` — the container runs immediately on start, then sleeps and repeats automatically. No cron, no external scheduler needed.

```yaml
environment:
  - RERUN_INTERVAL=24h    # run every 24 hours
restart: unless-stopped   # keep container alive between runs
```

**Supported interval formats:**

| Value | Meaning |
|---|---|
| `30m` | Every 30 minutes |
| `6h` | Every 6 hours |
| `12h` | Every 12 hours |
| `24h` | Every 24 hours |
| `1d` | Every day (same as 24h) |
| *(unset)* | Run once and exit |

Logs show each run number, timestamp, and next scheduled run time:

```
══════════════════════════════════════════════════════
  Run #1  —  2026-04-21 02:00:00
══════════════════════════════════════════════════════
  floating-posters  v1.9.0
  ...
  ✅  RedCurtains.mp4  saved to /output

  Next run: 2026-04-22 02:00:00
  Sleeping 24h...
```

If a run fails (non-zero exit), the container logs a warning and continues to the next scheduled run rather than crashing.

## Startup retry

When floating-posters starts at the same time as Radarr/Sonarr (e.g. on a fresh stack deploy or reboot), the *arr services may not be ready to accept API calls immediately even after their containers are running. The retry settings handle this gracefully:

| Variable | Default | Description |
|---|---|---|
| `STARTUP_RETRY_ATTEMPTS` | `5` | Number of connection attempts before giving up |
| `STARTUP_RETRY_DELAY` | `30` | Seconds to wait between attempts |

With defaults, floating-posters will wait up to **2.5 minutes** for Radarr/Sonarr to become available before failing. Each attempt is logged:

```
  ⚠  Radarr not ready (attempt 1/5): Connection refused
     Retrying in 30s...
  ⚠  Radarr not ready (attempt 2/5): Connection refused
     Retrying in 30s...
  [font] Poppins-Bold  size=15
  ...
```

If you're running floating-posters in the same docker-compose stack as Radarr and Sonarr, also add `depends_on` to ensure container start order:

```yaml
depends_on:
  - radarr
  - sonarr
  - nexroll
```

> **Note:** `depends_on` only guarantees that the Radarr/Sonarr *containers* start before floating-posters — not that the services inside them are ready. The retry logic handles the remaining gap.

## Scheduling with cron

If you prefer host-level cron over the built-in scheduler, leave `RERUN_INTERVAL` unset (`restart: "no"`) and use a crontab entry instead:

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
- Tags version releases (`v1.9.9`) as `:1.9.9` and `:1.9`

---

## Changelog

### v1.9.9
- **Duplicate registration prevention**: `nexroll_find_existing()` checks `GET /external/prerolls` before registering — skips re-registration if a preroll with the same path already exists; video file on disk is always updated by the render step regardless

### v1.9.8
- **`PYTHONUNBUFFERED=1`** added to Dockerfile and `python3 -u` used in entrypoint — ensures all log output is flushed immediately to Docker rather than being buffered and lost if the process exits

### v1.9.7
- Fixed NeXroll registration payload field name: `file_path` → `path` (API docs were wrong; actual validation schema requires `path`)
- Suppressed moviepy progress bar (`logger=None`) — removes noisy `▓▓▓ 37%` lines from Docker logs

### v1.9.6
- Added full response body logging on HTTP errors (422 etc.) to diagnose NeXroll API rejections
- Fixed `UnboundLocalError` on `cat_id` — moved debug print to after the category lookup call
- Category creation response now tries multiple ID field names (`id`, `category_id`, `category.id`)

### v1.9.5
- Switched NeXroll auth from `Authorization: Bearer` header to `?api_key=` query parameter — NeXroll only accepts the query param form despite documenting both
- Fixed categories response parsing to handle `{"categories": [...], "count": N}` wrapper returned by actual API

### v1.9.4
- NeXroll API calls now retry on 401 (not just connection errors) — handles NeXroll still initialising its auth system when floating-posters first starts
- `nexroll` added to `depends_on` in docker-compose sample

### v1.9.3
- Improved NeXroll error messages — distinguishes 401 (bad/missing key), 403 (read-only key), connection refused, and timeout as separate cases with actionable guidance

### v1.9.2
- **Startup retry**: Radarr and Sonarr connection attempts retry with configurable backoff (`STARTUP_RETRY_ATTEMPTS=5`, `STARTUP_RETRY_DELAY=30`) instead of immediately failing
- `depends_on: [radarr, sonarr, nexroll]` added to docker-compose sample
- Retry progress logged per-attempt with attempt count and remaining delay

### v1.9.1
- Documented both output modes in docker-compose and README: standalone (`/output` bind mount) vs NeXroll shared volume (`OUTPUT_DIR=/nexroll_media/Pre-Rolls`)

### v1.9.0
- **Built-in scheduler**: `RERUN_INTERVAL` (e.g. `24h`, `12h`, `6h`, `1d`, `30m`) keeps the container running and re-executes on a repeating schedule — no cron needed
- Each run is numbered and timestamped; next run time shown after completion
- Failed runs log a warning and continue rather than crashing

### v1.8.0
- **NeXroll integration**: registers rendered videos with NeXroll after each successful render
- Category lookup and auto-creation (`NEXROLL_CREATE_CATEGORY`)
- Optional immediate Plex sync (`NEXROLL_APPLY_TO_PLEX`)
- `NEXROLL_OUTPUT_PATH` maps container output path to the path NeXroll sees on the host

### v1.7.0
- **Multi-video scan-based processing**: one run handles all video+yaml pairs in `/input`
- **yaml-driven config**: all per-video settings move from docker-compose env vars to individual `.yaml` files — compose only needs connection/quality settings
- **Sonarr support**: `tv:` yaml key fetches upcoming TV series posters via Sonarr calendar API; `movie:` routes to Radarr

### v1.6.0
- Text wrapping for top/bottom messages (word-wraps at 85% of video width, each line centred)
- Multi-row poster layout: 6–10 posters split into 2 centred rows — 6 (3+3) · 7 (4+3) · 8 (4+4) · 9 (5+4) · 10 (5+5)
- `ROW_GAP` config for vertical spacing between rows; `NUM_POSTERS` max raised from 6 to 10

### v1.5.0
- `*_BG_COLOR` and `*_BG_OPACITY` for all three text areas (release date, top message, bottom message)
- `BG_OPACITY=0` removes the pill background entirely — text only, relies on shadow for legibility

### v1.4.0
- `FONT` config with 17 bundled fonts; Poppins-Bold is the default
- All font packages added to Dockerfile (`fonts-liberation`, `fonts-freefont-ttf`, `fonts-crosextra-*`); Poppins downloaded from Google Fonts at build time
- `TOP_MESSAGE` overlay with full parity to `BOTTOM_MESSAGE`
- `BOTTOM_MESSAGE_SHADOW` option

### v1.3.0
- Fixed release date not showing — text labels rearchitected as separate moviepy clips instead of being embedded in the poster RGBA image
- Date labels float in sync with their poster (same sine-wave phase)
- `BOTTOM_MESSAGE` overlay centered at bottom of frame, fades with poster group
- Date format changed to `April 20, 2026` style

### v1.2.0
- Python 3.13 base image; `apt-get upgrade` for patched openssl/libssl
- `CPU_THREADS` env var passes `-threads N` to FFmpeg; `deploy.resources.limits.cpus` caps the container

### v1.1.0
- `SHOW_RELEASE_DATE`, `RELEASE_DATE_COLOR`, `RELEASE_DATE_SIZE`, `RELEASE_DATE_SHADOW`
- Fixed `set_opacity` TypeError with moviepy 1.0.3 — replaced with `VideoClip` mask for proper per-frame fade with alpha channel preservation

### v1.0.0
- Initial release: Radarr API integration, floating sine-wave animation, configurable fade/shadow/rounded corners, multi-arch Docker image (amd64 + arm64)

---

## Credits

Built to work with [NeXroll](https://github.com/JFLXCLOUD/NeXroll) by JFLXCLOUD.  
Poster art sourced from Radarr and Sonarr via their v3 APIs.
