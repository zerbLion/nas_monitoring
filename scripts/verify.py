#!/usr/bin/env python3
# Cross-check the served temps.json against INDEPENDENT ground-truth sources on the NAS,
# so you can confirm the pulled data is actually correct (not just self-consistent):
#   CPU     : endpoint (Glances)  vs  raw sysfs k10temp        (bypasses Glances)
#   System  : endpoint            vs  synowebapi sys_temp      (DSM official value)
#   Disks   : endpoint (smartctl)  vs  synowebapi SYNO.Storage.CGI.Storage (DSM Storage Manager)
# Prints a PASS/FAIL table (±TOL C to absorb the ~30s refresh drift) and exits non-zero on mismatch.
#
# Run:  ssh nas 'python3 /volume1/docker/nas_monitoring/scripts/verify.py'
#       (override endpoint: ENDPOINT=http://192.168.1.100:8787/temps.json ... )
import os, sys, re, json, time, subprocess, urllib.request

ENDPOINT = os.environ.get("ENDPOINT", "http://localhost:8787/temps.json")
TOL = 3  # Celsius tolerance: endpoint data may be ~30s old and temps fluctuate

def priv(cmd):
    return cmd if os.geteuid() == 0 else ["sudo", "-n"] + cmd

def get_endpoint():
    with urllib.request.urlopen(ENDPOINT, timeout=5) as r:
        return json.load(r)

def sysfs_cpu():
    try:
        with open("/sys/class/hwmon/hwmon0/temp1_input") as f:
            return round(int(f.read().strip()) / 1000)
    except Exception:
        return None

def syno_sys_temp():
    try:
        out = subprocess.run(priv(["/usr/syno/bin/synowebapi", "--exec",
            "api=SYNO.Core.System", "method=info", "version=1"]),
            capture_output=True, text=True, timeout=8).stdout
        m = re.search(r'"sys_temp"\s*:\s*([0-9]+)', out)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def syno_disk_temps():
    res = {}
    try:
        out = subprocess.run(priv(["/usr/syno/bin/synowebapi", "--exec",
            "api=SYNO.Storage.CGI.Storage", "method=load_info", "version=1"]),
            capture_output=True, text=True, timeout=10).stdout
        for d in json.loads(out).get("data", {}).get("disks", []):
            if str(d.get("id", "")).startswith("sata"):
                res[d["id"]] = d.get("temp")
    except Exception:
        pass
    return res

def check(name, served, truth, src):
    if served is None or truth is None:
        verdict = "N/A "
        ok = False
    else:
        ok = abs(served - truth) <= TOL
        verdict = "PASS" if ok else "FAIL"
    print(f"  {name:8}  endpoint={str(served):>4}   {src} = {str(truth):>4}   -> {verdict}")
    return ok

def main():
    try:
        ep = get_endpoint()
    except Exception as e:
        print(f"接口不可达 {ENDPOINT}: {e}")
        sys.exit(2)
    age = int(time.time()) - ep.get("ts", 0)
    print(f"接口 {ENDPOINT}")
    print(f"数据采集于 {age}s 前 (刷新间隔 30s, 容差 ±{TOL}C)\n")
    ok = True
    ok &= check("CPU", ep.get("cpu"), sysfs_cpu(), "sysfs k10temp ")
    ok &= check("System", ep.get("system"), syno_sys_temp(), "synowebapi   ")
    dt = syno_disk_temps()
    for d in ep.get("disks", []):
        ok &= check(d["name"], d.get("temp"), dt.get(d["name"]), "DSM storage  ")
    print("\n结果: 全部与独立来源一致 ✅" if ok else
          "\n结果: 有项超出容差 ❌ (多为采集时差/波动, 复跑一次再看)")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
