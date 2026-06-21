#!/bin/bash
# Idempotent launcher for the temps collector daemon.
#   - If a live instance already runs (per daemon.pid), do nothing.
#   - Otherwise start temps_daemon.sh detached via setsid.
# Use for manual start AND as the DSM Task Scheduler boot-up command:
#     bash /volume1/docker/nas_monitoring/scripts/daemon_start.sh
DIR=/volume1/docker/nas_monitoring
PIDF="$DIR/daemon.pid"
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; then
  echo "temps daemon already running (pid $(cat "$PIDF"))"
  exit 0
fi
setsid bash "$DIR/scripts/temps_daemon.sh" </dev/null >>"$DIR/daemon.log" 2>&1 &
echo "temps daemon started"
exit 0
