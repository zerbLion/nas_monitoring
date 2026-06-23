<div align="center">

# 🌡️ nas_monitoring

[English](README.md) · **中文**

**把基于 AMD 的群晖 NAS 变成一个干净的温度 JSON 接口——CPU、主板、每块硬盘——直接喂给 ESP32 / M5Dial 桌面小屏。**

![Platform](https://img.shields.io/badge/platform-Synology%20DSM%207-0f62fe)
![CPU](https://img.shields.io/badge/CPU-AMD%20Ryzen%20(k10temp)-ed1c24)
![For](https://img.shields.io/badge/for-ESP32%20%2F%20M5Dial-00979d)
![Stack](https://img.shields.io/badge/stack-Shell%20%2B%20Python%203-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

<br/>

![M5Dial 显示实时 NAS 温度](docs/m5dial-mockup.svg)

</div>

---

## 🤔 为什么有这个项目

在 **AMD 群晖**（DS925+、DS1525+，凡是 Ryzen）上把温度读全，是一条处处半通的路：

- **Glances** 在 Docker 里能读到 **CPU**——但在这些机器上**读不到主板/系统温度**，而它读硬盘走的 hddtemp 在群晖容器里很不稳。
- 自带的 **`smartctl` 是 6.5**——没有 `--json`，`--scan` 还坏掉。不知道 `-d sat` 这个技巧就什么都读不出来。
- AMD 的 CPU 标签是 **`Tctl` / `k10temp`**，不是每篇 Intel 教程里照抄的 `Core 0` / `Package id 0`。

结果你只能把三个工具拼起来，还得**祈祷读数是对的**。

**`nas_monitoring` 给每个值挑对来源、合并成一个接口，并且把每一项都拿独立来源交叉核对过**——所以你确信它是对的，而 ESP32 只需拉一份整洁的 JSON。

## ✨ 你能拿到什么

```http
GET http://<你的NAS>:8787/temps.json
```
```json
{ "ts": 1718960000, "unit": "C", "cpu": 53, "cpu_label": "Tctl",
  "system": 53, "disks": [ {"name":"sata1","temp":39}, {"name":"sata2","temp":41}, {"name":"sata3","temp":40} ] }
```

- 🧠 **CPU** — Glances `/api/4/sensors`，AMD `Tctl`（k10temp）
- 🧩 **系统 / 主板** — 群晖原生 `synowebapi`（`sys_temp`，就是 DSM 界面那个值）
- 💽 **每块硬盘** — `smartctl -A -d sat`（SMART 属性 194）
- ✅ **可验证，不是拍脑袋** — `verify.py` 拿 sysfs、synowebapi、DSM 存储管理器交叉对账
- 🔁 **装好就不用管** — 采集守护进程每 30 秒刷新，Web 层重启自启
- 🪶 **轻** — shell + Python 3 + 两个小容器，无数据库、无 agent

## 🧭 架构

```
                       ┌──────────────── 群晖 NAS (AMD, DSM 7) ────────────────┐
   CPU 温度   ──►  Glances  (/api/4/sensors → "Tctl") ─┐                        │
 系统温度    ──►  synowebapi (SYNO.Core.System)      ─┼─► collect_temps.py ─► temps.json
 硬盘温度    ──►  smartctl -d sat (属性 194)          ─┘     (守护进程, 原子写)   │ │
                       │                                              nginx :8787 │
                       └──────────────────────────────────────────────────┬──────┘
                                                                           │ HTTP GET
                                                                           ▼
                                                              ESP32 / M5Dial  (ArduinoJson)
```
故意分两路：CPU 走 Glances（干净），硬盘走 `smartctl`（群晖容器里 hddtemp 不稳），主板温度走 `synowebapi`（Glances 在 AMD 上看不到它）。

## 🚀 快速开始

> 前提：NAS 已开 SSH、有可 `sudo` 的管理员、Container Manager（Docker）可用。

```bash
# 在 NAS 上（路径默认用标准的 /volume1/docker 共享文件夹）
git clone https://github.com/ZerbLion/nas_monitoring.git
cd nas_monitoring

# 1) Glances —— 必须 pid:host，否则传感器返回空
sudo docker compose -f glances/docker-compose.yml up -d

# 2) 找到你的 CPU 标签（AMD 预期是 "Tctl"），顺便确认传感器接口可用
curl -s http://localhost:61208/api/4/sensors

# 3) 放好采集脚本，再起 JSON 服务（守护进程 + DSM 开机任务见文档）
sudo docker compose -f serve/docker-compose.yml up -d

# 4) 拿独立来源把每个值核对一遍
python3 scripts/verify.py
```

然后用任意浏览器（或你的 ESP32）访问 `http://<你的NAS-IP>:8787/temps.json`。

### 🖥 实时面板

同一个 nginx 根目录里自带一个 `web/index.html`，打开服务器**根地址**就能看到上面那张表盘的**实时**版（无需打包、无需额外服务）：

```
http://<你的NAS-IP>:8787/          ← 实时表盘（CPU、系统、每块硬盘）
http://<你的NAS-IP>:8787/temps.json ← 原始 JSON（ESP32 拉这个）
```

每 5 秒刷新，按温度分区给每个读数上绿/琥珀/红色，用 `ts` 判断数据是否过期并显示状态点，
**点表盘可在 CPU → 系统 → 各硬盘之间循环切换**大显示（特意这么设计，方便以后接 M5Dial 旋钮）。
中间的型号取自 JSON 的 `model` 字段；放到别处时可用 `?model=...` 覆盖。

## 🔌 JSON 契约 + ESP32

负载刻意做得扁平、小巧，方便单片机低成本解析：

| 字段 | 类型 | 含义 |
|---|---|---|
| `cpu` / `cpu_label` | int / string | CPU 温度 + 传感器标签（`Tctl`） |
| `system` | int | 主板 / 系统温度 |
| `disks[].name` / `.temp` | string / int | 每块盘温度 |
| `ts` / `unit` | int / string | 采集 unix 时间 / `"C"`（用 `ts` 判断数据是否过期） |

```cpp
#include <HTTPClient.h>
#include <ArduinoJson.h>            // v7

void fetchTemps() {
  HTTPClient http;
  http.begin("http://<你的NAS-IP>:8787/temps.json");
  if (http.GET() == 200) {
    JsonDocument doc;
    if (!deserializeJson(doc, http.getStream())) {
      int cpu = doc["cpu"] | -1;          // 53
      int sys = doc["system"] | -1;       // 53
      for (JsonObject d : doc["disks"].as<JsonArray>())
        Serial.printf("%s = %d C\n", d["name"].as<const char*>(), d["temp"] | -1);
    }
  }
  http.end();
}
```

## ✅ 怎么验证的

`verify.py` 不信任管线本身——它从**另一条路**重新读每个值再比对：

| 值 | 接口来源 | 拿来对账的独立来源 |
|---|---|---|
| CPU | Glances | 直读 `sysfs` k10temp（绕开 Glances） |
| 系统 | synowebapi | synowebapi `sys_temp` |
| 硬盘 | smartctl | DSM 存储管理器（`SYNO.Storage.CGI.Storage`） |

```
CPU     endpoint=53   sysfs k10temp=53   -> PASS
System  endpoint=53   synowebapi   =53   -> PASS
sata1   endpoint=39   DSM storage  =39   -> PASS  ...
```

## 🔒 安全

接口（`8787`、Glances `61208`）**默认无认证、仅限内网**。务必只在内网用——**不要做端口转发、也不要用隧道把它们暴露到公网。** 特权读取走一条**限定范围**的 `NOPASSWD` sudoers，仅放行 `smartctl` / `docker` / `synowebapi`。

## 🗺 路线图与愿景

现在它只吐五个温度，但这套「一份 JSON」契约是奔着**给整台 NAS 配一个桌面物理表盘**去的——旋钮翻屏切换：

- **更多指标，同一契约** — 硬盘读写吞吐、网络 I/O、CPU/内存负载、风扇转速、卷容量、UPS 状态。
- **可组合** — 每个数据源是一个吐「标准结构」的小适配器，表盘不用重烧固件就能渲染任意一个。
- **填的是哪块空白** — 在*浏览器*里看 NAS 的工具很多（Glances、Netdata、Grafana、Scrutiny）；而一个常驻、无线、**摆在桌上的物理表盘**，还适配 AMD 群晖、还能接 API 组合的，几乎没有。

进度见 [TODO.md](TODO.md)。

## 📜 许可证

[MIT](LICENSE)。

---

<div align="center">

为家庭实验室 + ESP32 桌面小物件而造，作者 [**@ZerbLion**](https://github.com/ZerbLion)。<br/>
如果它帮你省下了一下午跟 `smartctl` 较劲的时间，给颗 ⭐ 就很开心了。

</div>
