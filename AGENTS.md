# AGENTS.md — 给 AI 协作者的操作指南

面向在本仓库工作的 AI 代理（Claude Code 等）。人类向导见 [README.md](README.md)；已完成版本见 [CHANGELOG.md](CHANGELOG.md)；待办见 [TODO.md](TODO.md)。

## 这是什么
群晖 NAS 温度监控：把 **CPU / 系统 / 3 块硬盘** 温度合并成一份 HTTP JSON，供 ESP32（M5Dial）拉取显示。
**线上状态**：已跑通并交叉验证通过。对外端点 `http://192.168.1.100:8787/temps.json`。

## 连接 NAS（关键）
- SSH 别名：`ssh nas`（= `<user>@192.168.1.100:22`，密钥 `~/.ssh/nas_ed25519`）。
- **免密已配好：不要再向用户索要 SSH/sudo 密码。**
- 限定范围免密 sudo：`/etc/sudoers.d/nas-monitoring` 仅放行 `smartctl` / `docker` / `synowebapi`，用 `sudo -n <全路径>`。
- `docker` 不在 PATH，用全路径 `/usr/local/bin/docker`。

## 数据三来源（改动务必照此）
| 项 | 命令 | 取值 |
|---|---|---|
| CPU | Glances `GET localhost:61208/api/4/sensors` | label `Tctl`（AMD k10temp；**不是** Intel 的 Core/Package） |
| 系统/主板 | `sudo -n /usr/syno/bin/synowebapi --exec api=SYNO.Core.System method=info version=1` | `sys_temp` |
| 硬盘 | `sudo -n /usr/bin/smartctl -A -d sat /dev/sataN` | 属性 `194` 第 10 列 |

## 平台特定坑（别踩）
- 本机 **DS1525+（AMD Ryzen，DSM 7.3.1）**，CPU 传感器是 `k10temp`，标签 `Tctl`/`Tdie`。
- **smartctl 是 6.5**：无 `-j` JSON；`--scan` 损坏；**必须 `-d sat`** 才读得到 ATA 属性表。
- Glances 必须 `pid: host`，否则读不到宿主机传感器（返回空）；它在本机**只吐 CPU**，主板温度读不到 → 走 synowebapi。
- busybox：**无 `pgrep`**；管理守护进程**按 PID `kill`，切勿 `pkill -f temps_daemon.sh`**（会自匹配启动器命令行而自杀）。
- `temps.json` 用「临时文件 + `mv`」原子替换。

## 运行 / 验证
```bash
ssh nas 'python3 /volume1/docker/nas_monitoring/scripts/collect_temps.py'   # 跑一次采集
ssh nas 'python3 /volume1/docker/nas_monitoring/scripts/verify.py'          # 交叉核对 PASS/FAIL
ssh nas 'kill -0 $(cat /volume1/docker/nas_monitoring/daemon.pid) && echo ALIVE'  # 守护进程存活
```

## 安全红线
- **密码绝不写进任何文件**（当前仓库无任何凭据，请保持）。
- 端点 `8787` / `61208` **无认证、仅内网**：不要在路由器 / Cloudflare 隧道把它们暴露公网。
- 改 sudoers / 容器 / 开机任务属系统改动，动手前与用户确认。

## 文件地图
- NAS：`/volume1/docker/glances/`（Glances）、`/volume1/docker/nas_monitoring/`（scripts + `web/temps.json`）。
- 仓库：`glances/`、`serve/`（compose）、`scripts/`（collect / daemon / verify 等）、`*.md`（文档）。
