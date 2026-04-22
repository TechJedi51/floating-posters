# ─────────────────────────────────────────────────────────────
# floating-posters  —  Radarr poster overlay for Plex prerolls
# ─────────────────────────────────────────────────────────────
FROM python:3.13-slim

LABEL org.opencontainers.image.title="floating-posters"
LABEL org.opencontainers.image.description="Overlays animated Radarr movie posters onto a background video for Plex prerolls"
LABEL org.opencontainers.image.source="https://github.com/TechJedi51/floating-posters"

# ── System dependencies ───────────────────────────────────────
# apt-get upgrade pulls in patched openssl / libssl
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
        ffmpeg \
        openssl \
        libssl3 \
        wget \
        # ── Font packages ─────────────────────────────────────
        fonts-dejavu-core \
        fonts-liberation \
        fonts-freefont-ttf \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
    && mkdir -p /usr/share/fonts/truetype/google-fonts \
    # ── Poppins (Google Fonts) ────────────────────────────────
    && wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf" \
            -O /usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf \
    && wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf" \
            -O /usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf \
    && wget -q "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf" \
            -O /usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf \
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

# ── Default environment ───────────────────────────────────────
ENV INPUT_VIDEO=/input/background.mp4
ENV OUTPUT_VIDEO=/output/output.mp4
ENV START_TIME=2.0
ENV POSTER_DURATION=8.0
ENV FADE_DURATION=0.75
ENV NUM_POSTERS=4
ENV UPCOMING_DAYS=180
ENV POSTER_WIDTH=185
ENV PADDING=28
ENV ROW_GAP=24
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
ENV CPU_THREADS=2
ENV FONT=Poppins-Bold
ENV SHOW_RELEASE_DATE=true
ENV RELEASE_DATE_COLOR=#FFFFFF
ENV RELEASE_DATE_SIZE=15
ENV RELEASE_DATE_SHADOW=true
ENV RELEASE_DATE_BG_COLOR=#000000
ENV RELEASE_DATE_BG_OPACITY=170
ENV BOTTOM_MESSAGE_SHOW=false
ENV BOTTOM_MESSAGE=
ENV BOTTOM_MESSAGE_ADD_DATE=true
ENV BOTTOM_MESSAGE_COLOR=white
ENV BOTTOM_MESSAGE_SIZE=15
ENV BOTTOM_MESSAGE_SHADOW=false
ENV BOTTOM_MESSAGE_BG_COLOR=#000000
ENV BOTTOM_MESSAGE_BG_OPACITY=170
ENV TOP_MESSAGE_SHOW=false
ENV TOP_MESSAGE=
ENV TOP_MESSAGE_ADD_DATE=false
ENV TOP_MESSAGE_COLOR=white
ENV TOP_MESSAGE_SIZE=15
ENV TOP_MESSAGE_SHADOW=false
ENV TOP_MESSAGE_BG_COLOR=#000000
ENV TOP_MESSAGE_BG_OPACITY=170

ENTRYPOINT ["python3", "floating_posters.py"]
