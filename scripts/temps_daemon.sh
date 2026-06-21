#!/bin/bash
# Persistent collector loop: refresh web/temps.json every INTERVAL seconds (atomic write).
#
# Singleton via PID file. NOTE: busybox has no pgrep, and do NOT use
# `pkill -f temps_daemon.sh` to manage it -- the pattern self-matches the launcher's
# own command line (which contains this path) and kills it. Stop by PID instead.
#
# Start now via setsid (see scripts/daemon_start.sh); start on boot via DSM Task
# Scheduler (boot-up trigger) -> see README §8.
set -u
DIR=/volume1/docker/nas_monitoring
INTERVAL="${INTERVAL:-30}"
OUT="$DIR/web/temps.json"
TMP="$DIR/web/.temps.json.tmp"
PIDF="$DIR/daemon.pid"
mkdir -p "$DIR/web"
# singleton guard: exit quietly if a live instance already owns the pidfile
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; then
  exit 0
fi
echo $$ > "$PIDF"
trap 'rm -f "$PIDF"' EXIT
while :; do
  if python3 "$DIR/scripts/collect_temps.py" > "$TMP" 2>>"$DIR/daemon.err"; then
    mv -f "$TMP" "$OUT"
  fi
  sleep "$INTERVAL"
done
