#!/bin/sh
# ─────────────────────────────────────────────────────────────
# entrypoint.sh  —  floating-posters scheduler
#
# RERUN_INTERVAL not set  → run once and exit  (default)
# RERUN_INTERVAL=6h       → run every 6 hours
# RERUN_INTERVAL=12h      → run every 12 hours
# RERUN_INTERVAL=24h      → run every 24 hours
# RERUN_INTERVAL=1d       → same as 24h  (d suffix = days)
# RERUN_INTERVAL=30m      → run every 30 minutes (useful for testing)
#
# Supports: m (minutes), h (hours), d (days)
# ─────────────────────────────────────────────────────────────

parse_interval() {
    raw="$1"
    # Extract numeric part and unit suffix
    num=$(echo "$raw" | sed 's/[^0-9]//g')
    unit=$(echo "$raw" | sed 's/[0-9]//g' | tr '[:upper:]' '[:lower:]')

    if [ -z "$num" ] || [ "$num" -le 0 ] 2>/dev/null; then
        echo ""
        return
    fi

    case "$unit" in
        m|min|mins|minute|minutes) echo $((num * 60)) ;;
        h|hr|hrs|hour|hours)       echo $((num * 3600)) ;;
        d|day|days)                echo $((num * 86400)) ;;
        "")                        echo $((num * 3600)) ;;   # bare number = hours
        *) echo "" ;;
    esac
}

# ── Run-once mode ─────────────────────────────────────────────
if [ -z "$RERUN_INTERVAL" ]; then
    echo "┌─────────────────────────────────────────────────────┐"
    echo "│  floating-posters  —  single run mode               │"
    echo "└─────────────────────────────────────────────────────┘"
    exec python3 -u /app/floating_posters.py
fi

# ── Scheduled loop mode ───────────────────────────────────────
SLEEP_SECS=$(parse_interval "$RERUN_INTERVAL")

if [ -z "$SLEEP_SECS" ]; then
    echo "ERROR: Invalid RERUN_INTERVAL '$RERUN_INTERVAL'"
    echo "       Use format: 30m  6h  12h  24h  1d"
    exit 1
fi

# Human-readable interval for the log
if [ "$SLEEP_SECS" -ge 86400 ] && [ $((SLEEP_SECS % 86400)) -eq 0 ]; then
    INTERVAL_LABEL="$((SLEEP_SECS / 86400))d"
elif [ "$SLEEP_SECS" -ge 3600 ] && [ $((SLEEP_SECS % 3600)) -eq 0 ]; then
    INTERVAL_LABEL="$((SLEEP_SECS / 3600))h"
else
    INTERVAL_LABEL="$((SLEEP_SECS / 60))m"
fi

echo "┌─────────────────────────────────────────────────────┐"
echo "│  floating-posters  —  scheduled mode                │"
printf "│  Interval: %-41s│\n" "$INTERVAL_LABEL"
echo "└─────────────────────────────────────────────────────┘"

RUN=1
while true; do
    echo ""
    echo "══════════════════════════════════════════════════════"
    echo "  Run #${RUN}  —  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "══════════════════════════════════════════════════════"

    python3 /app/floating_posters.py
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "  ⚠  Run #${RUN} exited with code ${EXIT_CODE} — will retry next interval"
    fi

    NEXT=$(date -d "@$(($(date +%s) + SLEEP_SECS))" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
           || date -r $(($(date +%s) + SLEEP_SECS)) '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
           || echo "in ${INTERVAL_LABEL}")

    echo ""
    echo "  Next run: ${NEXT}"
    echo "  Sleeping ${INTERVAL_LABEL}..."
    echo ""

    RUN=$((RUN + 1))
    sleep "$SLEEP_SECS"
done
