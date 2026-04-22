# 🎬 floating-posters  `v1.9.2`

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

> **Tip:** If floating-posters is in the same stack as Radarr and Sonarr, add `depends_on: [radarr, sonarr]` to ensure container start order. The `STARTUP_RETRY_ATTEMPTS` and `STARTUP_RETRY_DELAY` env vars handle the gap between a container starting and the service being ready to accept API calls.

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
- Tags version releases (`v1.9.2`) as `:1.9.2` and `:1.9`

---

## Changelog

### v1.9.2
- **Startup retry**: Radarr and Sonarr connection attempts now retry with configurable delay (`STARTUP_RETRY_ATTEMPTS=5`, `STARTUP_RETRY_DELAY=30`) instead of immediately failing — handles the gap between container start and service readiness
- **`depends_on`** added to docker-compose sample so Radarr/Sonarr containers start before floating-posters
- Retry progress logged per-attempt with attempt count and delay

### v1.9.1
- Clarified output configuration in `docker-compose.yml` and README — documented both standalone (`/output` bind mount) and NeXroll shared volume (`OUTPUT_DIR` + `NEXROLL_OUTPUT_PATH`) setups
- `OUTPUT_DIR` env var documented as the correct way to redirect output when using a shared volume with NeXroll

### v1.9.0
- **Built-in scheduler**: `RERUN_INTERVAL` env var (e.g. `24h`, `12h`, `6h`, `1d`, `30m`) keeps the container running and re-executes on a repeating schedule
- Supports `m` (minutes), `h` (hours), `d` (days) suffixes
- Each run is numbered and timestamped in the log; next run time is shown after each completion
- Failed runs log a warning and continue rather than crashing the container
- `restart: unless-stopped` in docker-compose replaces `restart: "no"` when using the scheduler

### v1.8.0
- **NeXroll integration**: after each render, optionally register the output as a preroll in NeXroll via `POST /external/prerolls/register`
- Category lookup via `GET /external/categories`; auto-creates category if not found (`NEXROLL_CREATE_CATEGORY`)
- Optional immediate Plex sync via `POST /external/apply-category/{id}` (`NEXROLL_APPLY_TO_PLEX`)
- `NEXROLL_OUTPUT_PATH` maps container `/output` to the host path NeXroll can access
- NeXroll URL shown in startup log if configured

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
