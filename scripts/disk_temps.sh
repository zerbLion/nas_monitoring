#!/bin/bash
# Step 4 — Read SMART temperature for the 3 SATA disks and print JSON.
#
# Why "-d sat": Synology exposes disks as /dev/sataN behind a SAT layer; smartctl
#   needs "-d sat" to get the ATA SMART attribute table (attribute 194 = Temperature).
#   (smartctl --scan is broken on the bundled smartctl 6.5, so devices are listed explicitly.)
# Why sudo: reading SMART needs root. Runs smartctl directly if already root, otherwise
#   via "sudo -n" (relies on scoped NOPASSWD in /etc/sudoers.d/nas-monitoring).
#
# Output: JSON array, e.g.
#   [{"name":"sata1","model":"Synology HAT3310-16T","serial":"...","temp_c":39}, ...]
# Override disks with: DISKS="sata1 sata2" ./disk_temps.sh
set -u
SMARTCTL=/usr/bin/smartctl
DISKS="${DISKS:-sata1 sata2 sata3}"
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo -n"; fi

emit_entry() {
  local d="$1" info model serial temp temp_json
  info=$($SUDO "$SMARTCTL" -i -A -d sat "/dev/$d" 2>/dev/null)
  model=$(printf '%s\n' "$info"  | grep -E 'Product:|Device Model:|Model Number:' | head -1 | sed 's/.*: *//; s/[[:space:]]*$//')
  serial=$(printf '%s\n' "$info" | grep -iE 'Serial number:' | head -1 | sed 's/.*: *//; s/[[:space:]]*$//')
  temp=$(printf '%s\n' "$info"   | awk '$1==194 || $1==190 {print $10; exit}')
  [ -n "${temp:-}" ] && temp_json="$temp" || temp_json="null"
  printf '{"name":"%s","model":"%s","serial":"%s","temp_c":%s}' "$d" "${model:-}" "${serial:-}" "$temp_json"
}

printf '['
first=1
for d in $DISKS; do
  [ "$first" -eq 1 ] && first=0 || printf ','
  emit_entry "$d"
done
printf ']\n'
