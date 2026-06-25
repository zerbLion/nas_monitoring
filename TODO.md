# TODO

已完成版本见 [CHANGELOG.md](CHANGELOG.md)。

## 近期
- [ ] 验证开机自启任务（DSM 任务计划 "TimeMonitory"）：先 `ssh nas 'kill $(cat /volume1/docker/nas_monitoring/daemon.pid)'` 再点「运行」，确认端点 `ts` 刷新。
- [ ] nginx 加响应头 `Cache-Control: no-store`、`Content-Type: application/json`（防 ESP32 端缓存）。
- [ ] 数据陈旧标记：守护进程挂掉时端点能体现（ESP32 目前可用 `ts` 自行判断）。

## 开源化准备
- [ ] 把内网 IP `192.168.1.100`、用户 `<user>`、盘符/标签抽成 `config` / 环境变量（出现处：README.md、scripts/verify.py、serve/docker-compose.yml）。
- [ ] 加 `LICENSE`、`.env.example`、安装说明（适配其它型号 / 盘数 / Intel 机型的标签差异）。
- [ ] 卖点定位：突出 **AMD 群晖** 的踩坑合集（`k10temp/Tctl`、`smartctl 6.5 必须 -d sat`、`--scan` 损坏、`synowebapi sys_temp`、Glances `pid host`）。

## ESP32 / M5Dial 端
- [ ] 写 M5Dial 固件：`HTTPClient` 拉端点 + ArduinoJson 解析 + 圆屏显示（README §4 有示例）。
- [ ] 旋钮翻屏 / 选数据源。

## 更多数据源（同一份 JSON 契约扩展）
- 前端**已就绪**：`web/index.html` 已能渲染容量 / SMART 健康 / CPU 负载 / 内存 / 网络 / RAID / 风扇 / UPS（有字段就亮）。扩展契约见 [INTEGRATION.md](INTEGRATION.md)「扩展契约」。**剩下是后端采集**：
- [ ] DSM 开 SNMP（控制面板 → 终端机和 SNMP），设只读 community。
- [ ] `collect_temps.py` 加 SMART 健康：复用现成 `smartctl -A -d sat` 输出，多解析属性 5/197/198 → 每盘 `health: ok|warn|crit`（零额外命令）。
- [ ] `collect_temps.py` 加 SNMP `snmpwalk 1.3.6.1.4.1.6574`：卷容量(`…102`)、CPU/内存、RAID(`…3`)、UPS(`…5`)、风扇 → 填扩展字段。
- [ ] 每个源做成「标准 reading」适配器，旋钮翻屏切换，新增源不用重烧固件。

## 平台化（远期，见对话里的「合璧」设想）
- [ ] 定 `spec/`：通用 `reading` schema + manifest，给 nas-temps 加 `/v1/readings` 通用端点。
- [ ] 上层 `deskpanel/` 伞仓库：`device/`(M5Dial) + `hub/`(NAS) + `providers/` + `companion/`。
