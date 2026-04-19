#!/bin/sh
set -e

APP_UID="${PUID:-1000}"
APP_GID="${PGID:-1000}"
APP_DATA_DIR="${APP_CONFIG_DIR:-/app/data}"

mkdir -p "$APP_DATA_DIR"
chown -R "$APP_UID:$APP_GID" "$APP_DATA_DIR" /app || true

exec gosu "$APP_UID:$APP_GID" python /app/main.py
