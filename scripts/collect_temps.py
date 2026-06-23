#!/usr/bin/env python3
# Step 5 collector — merge CPU (Glances) + system (synowebapi) + disk (smartctl)
# temperatures into ONE JSON document, printed to stdout. This is the data source
# the ESP32 ultimately pulls (served as a static file by the nginx container).
#
# Sources:
#   CPU      : Glances REST  http://localhost:61208/api/4/sensors  -> label "Tctl" (AMD k10temp)
#   System   : synowebapi    SYNO.Core.System -> "sys_temp" (DSM's "System Temperature")
#   Disks    : smartctl -A -d sat /dev/sataN  -> attribute 194 (Temperature)
#
# Privilege: smartctl & synowebapi need root. Runs them directly if already root
# (e.g. launched by cron as root), otherwise via "sudo -n" (scoped NOPASSWD).
#
# Output shape (integers in Celsius; null if a source is unavailable):
#   {"ts":1718960000,"unit":"C","model":"DS1525+","cpu":54,"cpu_label":"Tctl","system":53,
#    "disks":[{"name":"sata1","temp":39},{"name":"sata2","temp":41},{"name":"sata3","temp":40}]}
import os, sys, re, json, time, subprocess, urllib.request

GLANCES_URL = "http://localhost:61208/api/4/sensors"
SMARTCTL    = "/usr/bin/smartctl"
SYNOWEBAPI  = "/usr/syno/bin/synowebapi"
DISKS       = ["sata1", "sata2", "sata3"]
CPU_LABELS  = ("Tctl", "Tdie")          # AMD k10temp; prefer Tctl, fall back to Tdie


def _priv(cmd):
    """Prefix with sudo -n unless we are already root."""
    return cmd if os.geteuid() == 0 else (["sudo", "-n"] + cmd)


def cpu_temp():
    try:
        with urllib.request.urlopen(GLANCES_URL, timeout=4) as r:
            data = json.load(r)
        labels = {d.get("label"): d.get("value") for d in data if isinstance(d, dict)}
        for lab in CPU_LABELS:
            v = labels.get(lab)
            if v is not None:
                return round(float(v)), lab
    except Exception as e:
        print(f"cpu_temp error: {e}", file=sys.stderr)
    return None, None


def system_info():
    """One synowebapi call -> (system_temp:int|None, model:str|None)."""
    try:
        p = subprocess.run(
            _priv([SYNOWEBAPI, "--exec", "api=SYNO.Core.System", "method=info", "version=1"]),
            capture_output=True, text=True, timeout=8)
        temp = re.search(r'"sys_temp"\s*:\s*([0-9]+)', p.stdout)
        model = re.search(r'"model"\s*:\s*"([^"]+)"', p.stdout)
        return (int(temp.group(1)) if temp else None,
                model.group(1) if model else None)
    except Exception as e:
        print(f"system_info error: {e}", file=sys.stderr)
    return None, None


def disk_temp(dev):
    try:
        p = subprocess.run(
            _priv([SMARTCTL, "-A", "-d", "sat", f"/dev/{dev}"]),
            capture_output=True, text=True, timeout=10)
        for line in p.stdout.splitlines():
            f = line.split()
            # ATA attribute table: col1=ID, col10=RAW_VALUE (first token = current temp)
            if len(f) >= 10 and f[0] in ("194", "190"):
                return int(f[9])
    except Exception as e:
        print(f"disk_temp {dev} error: {e}", file=sys.stderr)
    return None


def collect():
    cpu, lab = cpu_temp()
    sys_temp, model = system_info()
    return {
        "ts": int(time.time()),
        "unit": "C",
        "model": model,
        "cpu": cpu,
        "cpu_label": lab,
        "system": sys_temp,
        "disks": [{"name": d, "temp": disk_temp(d)} for d in DISKS],
    }


if __name__ == "__main__":
    print(json.dumps(collect()))
