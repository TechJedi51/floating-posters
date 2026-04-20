# ─────────────────────────────────────────────────────────────
# floating-posters  —  Radarr poster overlay for Plex prerolls
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="floating-posters"
LABEL org.opencontainers.image.description="Overlays animated Radarr movie posters onto a background video for Plex prerolls"
LABEL org.opencontainers.image.source="https://github.com/YOUR_USERNAME/floating-posters"

# ── System dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App ───────────────────────────────────────────────────────
COPY app/ .

# ── Volume mount points ───────────────────────────────────────
# /input   — place your background video here
# /output  — rendered output video appears here
VOLUME ["/input", "/output"]

# ── Default environment (overridden by docker-compose or -e flags) ──
ENV INPUT_VIDEO=/input/background.mp4
ENV OUTPUT_VIDEO=/output/output.mp4
ENV START_TIME=2.0
ENV POSTER_DURATION=8.0
ENV FADE_DURATION=0.75
ENV NUM_POSTERS=4
ENV UPCOMING_DAYS=180
ENV POSTER_WIDTH=185
ENV PADDING=28
ENV VERTICAL_POS=0.52
ENV CORNER_RADIUS=10
ENV ADD_SHADOW=true
ENV SHADOW_OFFSET_X=7
ENV SHADOW_OFFSET_Y=9
ENV SHADOW_BLUR=9
ENV SHADOW_OPACITY=175
ENV FLOAT_AMPLITUDE=14.0
ENV FLOAT_SPEED=0.55
ENV VIDEO_CRF=18
ENV VIDEO_PRESET=fast

ENTRYPOINT ["python3", "floating_posters.py"]
