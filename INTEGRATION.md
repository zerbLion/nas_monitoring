# INTEGRATION.md — 把 nas_monitoring 作为一个模块接入 deskstage / dial 设备

> 给**上层项目（deskstage / dial 设备）**的协作 AI 看的交接文档。
> 这里是「怎么消费本模块」；本仓库内部怎么干活见 [AGENTS.md](AGENTS.md)，卖点/安装见 [README.md](README.md)。
> **一句话**：本模块把一台 AMD 群晖 NAS 的温度（CPU / 系统 / 每块硬盘）变成一份扁平 JSON，并自带一个零依赖的实时表盘网页。上层只需消费这两样东西，**不要**耦合采集内部实现。

## 模块对外暴露的两样东西（这就是全部接口面）

| # | 产物 | 地址 | 性质 |
|---|---|---|---|
| 1 | **数据契约** `temps.json` | `http://<nas>:8787/temps.json` | **稳定** —— 按本文「JSON 契约」消费 |
| 2 | **表盘网页** `web/index.html` | `http://<nas>:8787/` | 自包含单文件，可直接 iframe / 复用其渲染逻辑 |

`<nas>` = LAN `192.168.1.100` 或 Tailscale `100.105.65.9`，端口固定 `8787`。

## JSON 契约（这是稳定接口，请只依赖它）

```json
{ "ts": 1782204327, "unit": "C", "model": "DS1525+",
  "cpu": 56, "cpu_label": "Tctl", "system": 56,
  "disks": [ {"name":"sata1","temp":44}, {"name":"sata2","temp":45}, {"name":"sata3","temp":45} ] }
```

| 字段 | 类型 | 含义 / 消费约定 |
|---|---|---|
| `ts` | int (unix 秒) | 采集时刻。**用它判过期**：`now - ts > 90s` 视为陈旧（守护进程每 30s 刷新一次）。|
| `unit` | string | 恒为 `"C"`（摄氏）。|
| `model` | string\|null | NAS 型号（表盘中央显示）。可能为 null，需容错。|
| `cpu` / `cpu_label` | int\|null / string | CPU 温度 + 传感器标签（AMD = `Tctl`）。|
| `system` | int\|null | 主板/系统温度。|
| `disks[]` | array | 每块盘 `{name, temp}`；**长度可变**（盘数随机型而变），消费方必须按数组遍历，**不要写死 3 块**。|

约定：任何温度源不可用时该值为 `null` —— 渲染前判空，别假设一定有数。

## 扩展契约（进行中，**向后兼容**）

温度之外还会逐步加入更多 NAS 指标（卷容量 / 磁盘 SMART 健康 / CPU 负载 / 内存 / 网络 / RAID / 风扇 / UPS）。原则：**上面的字段永不变形**，新指标一律作为**可选新字段**追加；消费方判存在再渲染（缺失 = 该源未接入，不是错误）。`web/index.html` 已按此实现（有则亮、无则隐藏）。

```jsonc
{
  // —— 现有字段不动（见上）——
  "disks":[{"name":"sata1","temp":42,"health":"ok"}],   // 盘对象新增可选 health: ok|warn|crit（由 SMART 属性 5/197/198 推断）

  // —— 以下全部可选 ——
  "uptime": 1083600,                                              // 秒
  "load":   {"cpu_pct":14,"mem_pct":41,"mem_used_mb":6700,"mem_total_mb":16384},
  "volumes":[{"name":"volume1","used_pct":63,"used_gb":5600,"total_gb":8900,"status":"normal"}],
  "raid":   [{"name":"Storage Pool 1","level":"SHR-1","status":"normal"}],  // status: normal|degraded|rebuilding|critical
  "net":    {"rx_mbps":48.2,"tx_mbps":6.4},
  "fans":   [{"name":"System","rpm":1180,"status":"ok"}],
  "ups":    {"present":true,"charge_pct":100,"load_pct":18,"runtime_s":3600,"on_battery":false}
}
```

百分比类指标（容量 / CPU 负载 / 内存）配色阈值：`green <70%`、`amber 70–90%`、`red >90%`。状态类字段（health / RAID status / fan status）按 `ok|normal|healthy`→绿、`warn|warning|degraded`→琥珀、`crit|critical|failed`→红 映射。数据来源主要靠群晖内置 SNMP（OID 树 `1.3.6.1.4.1.6574.*`）+ 现成 `smartctl`，详见 [TODO.md](TODO.md)「更多数据源」。

## 把它当 dial 设备的一个「数据源模块」

dial 设备的设想是「一份 JSON 契约 + 旋钮翻屏切换多个 reading」（见 [TODO.md](TODO.md) 平台化一节）。本模块就是其中一个 provider。接入时建议这样抽象：

- 把每个温度规整成一个统一 reading：`{ key, label, tag?, value, unit, zone }`
  - `zone` 按阈值算：`green <66°`，`amber 66–81°`，`red >81°`（与表盘 `SCALE_MAX=95` 一致）。
- CPU→System→各 disk 依次成为可翻屏的条目；`web/index.html` 里已实现这套（`temps[]` 数组 + 点表盘 `sel=(sel+1)%len` 循环），**旋钮只需映射到这个切换**，是为 M5Dial 预留的。
- 颜色/阈值/全量程都集中在 `web/index.html` 顶部常量（温度 `T_GREEN/T_AMBER/SCALE_MAX`、百分比 `P_GREEN/P_AMBER`），复用时照搬即可。

### 复用表盘的两条路
1. **直接嵌**：把 `http://<nas>:8787/` 用 iframe 放进 deskstage 面板；支持 `?model=...` 覆盖中央型号。最省事。
2. **吸收渲染逻辑**：`web/index.html` 是单文件、无构建、无外部依赖（纯原生 SVG + JS）。要做成 deskstage 的组件，直接搬里面的 gauge 几何（`polar()/arc()`）、圆环 `ringSVG()/setRing()`、配色 `tColor()/pColor()/okColor()` 即可。

## 部署 / 运行（本模块已在线，通常无需你动）

- 已部署：上面两个地址现在就是活的（nginx 容器 `restart: unless-stopped`，开机自启）。
- 重新部署本模块的改动：在配好 `ssh nas` 的机器上 `bash scripts/deploy_dashboard.sh`（详见 [AGENTS.md](AGENTS.md)）。
- **安全红线**：`8787` 无认证、仅内网/Tailscale。**deskstage 侧也不要把它代理/转发到公网。**

## 边界：能依赖什么、别碰什么

- ✅ 可依赖：上面的 **JSON 契约** 字段与语义、`8787/` 与 `8787/temps.json` 两个地址、表盘的 `?model=` 参数。
- ⛔ 别耦合：`scripts/`（collect / daemon / verify）是采集内部实现，命令、解析、sudo 细节随平台可能变，**不要从上层直接调它们**——只读 HTTP 端点。
- 🔜 未来契约升级：若加新指标，计划走「同一 JSON 形状的新字段 / 通用 `/v1/readings` 端点」(见 [TODO.md](TODO.md) 平台化)，会保持 `temps.json` 向后兼容。

## 文档导航
- 本文 `INTEGRATION.md` — 上层如何消费（你在这）
- [README.md](README.md) / [README.zh-CN.md](README.zh-CN.md) — 项目卖点、安装、ESP32 示例
- [AGENTS.md](AGENTS.md) — 本仓库 AI 运维（SSH、数据源命令、平台坑、部署脚本）
- [CHANGELOG.md](CHANGELOG.md) / [TODO.md](TODO.md) — 已完成版本 / 路线图（含平台化设想）
