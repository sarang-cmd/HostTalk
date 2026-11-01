#!/usr/bin/env bash
# Install HostTalk as a systemd service on Linux.
# Run as root after copying the checkout to /opt/hosttalk.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/hosttalk}
DATA_DIR=${DATA_DIR:-/var/lib/hosttalk}
SERVICE_USER=${SERVICE_USER:-hosttalk}

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this with sudo."
  exit 1
fi

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 "$DATA_DIR"

if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
  "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
  "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
fi

install -m 0644 "$APP_DIR/deploy/hosttalk.service" /etc/systemd/system/hosttalk.service
systemctl daemon-reload
systemctl enable --now hosttalk.service
echo "HostTalk runs as $SERVICE_USER. Data lives in $DATA_DIR."
echo "Open http://127.0.0.1:7284/console on this machine to set the password."
