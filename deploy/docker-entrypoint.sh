#!/bin/sh
# Start the room. Setup runs on first boot when no config file exists yet.
set -e
if [ ! -f "$HOSTTALK_HOME/config.json" ]; then
  if [ -z "$SERVER_PASSWORD" ]; then
    echo "First run needs SERVER_PASSWORD. Set it in the compose file or the environment."
    exit 1
  fi
  python -m hosttalk setup \
    --password "$SERVER_PASSWORD" \
    --room "${HOSTTALK_ROOM_NAME:-Front room}" \
    --port "${HOSTTALK_PORT:-7284}" \
    --non-interactive
fi
exec python -m hosttalk serve --headless --host 0.0.0.0
