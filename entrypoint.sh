#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

case "$PUID" in
    "" | *[!0-9]*)
        echo "PUID must be a numeric user id, got '$PUID'" >&2
        exit 1
        ;;
esac

case "$PGID" in
    "" | *[!0-9]*)
        echo "PGID must be a numeric group id, got '$PGID'" >&2
        exit 1
        ;;
esac

if [ "$(id -u)" = "0" ]; then
    # Create required directories
    mkdir -p /app/config/yubal /app/config/ytdlp /app/data

    # Fix ownership (non-recursive on /app/data to avoid slow startup with large libraries)
    chown "$PUID:$PGID" /app/data
    chown -R "$PUID:$PGID" /app/config

    exec gosu "$PUID:$PGID" "$@"
fi

# Non-root: still create dirs if possible, then exec
mkdir -p /app/config/yubal /app/config/ytdlp /app/data 2>/dev/null || true
exec "$@"
