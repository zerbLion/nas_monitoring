# AGENTS.md — 给 AI 协作者的操作指南

面向在本仓库工作的 AI 代理（Claude Code 等）。人类向导见 [README.md](README.md)；已完成版本见 [CHANGELOG.md](CHANGELOG.md)；待办见 [TODO.md](TODO.md)。

> **上层项目（deskstage / dial 设备）的 AI 请先读 [INTEGRATION.md](INTEGRATION.md)** —— 那里是「怎么把本模块当数据源消费」的稳定契约；本文是仓库内部运维细节。

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
- NAS：`/volume1/docker/glances/`（Glances）、`/volume1/docker/nas_monitoring/`（scripts + `web/`）。
- 仓库：`glances/`、`serve/`（compose）、`scripts/`（collect / daemon / verify 等）、`web/`（`index.html` 实时表盘）、`*.md`（文档）。

## 实时表盘 `web/index.html`（2026-06 新增）
- 自包含单文件，放在 nginx 根目录 → 打开 `http://192.168.1.100:8787/`（或 Tailscale `100.105.65.9:8787/`）即渲染表盘。
- 同源 fetch `temps.json`，每 5s 刷新；按温度分区上色（绿 <66 / 琥珀 66–81 / 红 >81，与 `SCALE_MAX=95` 对应）；用 `ts` 判定过期（>90s 显红点）。
- **点表盘**在 CPU→System→各硬盘间循环切换大显示（为日后 M5Dial 旋钮预留）。
- 中央型号读 JSON 的 `model` 字段；`collect_temps.py` 已在 `system_info()` 里从 synowebapi 一并解析出 `model`。可用 `?model=...` 覆盖。

## 部署实时表盘 —— 一条命令
在配好 `ssh nas` 别名的机器上 `git pull` 后，直接跑：
```bash
bash scripts/deploy_dashboard.sh
```
它会：①scp 页面+采集脚本到 NAS ②重采一次写出带 `model` 的 `temps.json` ③`verify.py` 交叉核对。
没配 `ssh nas` 别名时用 `SSH_HOST=用户名@100.105.65.9 bash scripts/deploy_dashboard.sh`。
nginx 只读挂载，无需重启容器；完事打开 `http://192.168.1.100:8787/` 刷新即可。
