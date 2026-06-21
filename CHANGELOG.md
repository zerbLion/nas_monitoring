# CHANGELOG

已完成的大版本。进行中/待办见 [TODO.md](TODO.md)。

## v1.0 — 2026-06-21 ✅ 首个可用版本
群晖 NAS 温度监控全链路打通并交叉验证通过。

- **环境**：群晖 DS1525+（AMD Ryzen，DSM 7.3.1）；SSH 密钥免密 + 限定范围免密 sudo（`/etc/sudoers.d/nas-monitoring`）。
- **数据源**：
  - CPU 温度 ← Glances `/api/4/sensors`，label `Tctl`（AMD k10temp）
  - 系统/主板温度 ← `synowebapi` `SYNO.Core.System` → `sys_temp`（Glances 在 AMD 上读不到，故改此路）
  - 3 块硬盘温度 ← `smartctl -A -d sat /dev/sataN`（属性 194）
- **合并 + 服务**：`collect_temps.py` 合并 → 守护进程（`temps_daemon.sh`）每 30s 原子写 `temps.json` → nginx 容器 `:8787` 暴露。
- **对外端点**：`http://192.168.1.100:8787/temps.json`（字段 `cpu` / `system` / `disks[]` / `ts` / `unit`）。
- **持久化**：Glances 与 nginx 容器 `restart: unless-stopped`；守护进程经 DSM 任务计划开机自启（任务名 "TimeMonitory"）。
- **验证**：`verify.py` 用独立来源（sysfs k10temp / synowebapi / DSM 存储管理器）交叉对账，**5 项全 PASS**。
