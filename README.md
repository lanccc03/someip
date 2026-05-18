# SOME/IP GUI Test Tool

这是一个基于 Python/PySide 的 SOME/IP 手工测试工具。当前 MVP-1 支持导入服务 JSON、启动/停止服务、Offer/Find Service、订阅/取消订阅 Eventgroup、发布 Event、Field Getter/Notifier、运行日志和消息 Trace 导出。

默认启动使用 `mock` 后端，只做本地模拟，不会发真实 SOME/IP 报文。需要 Wireshark 抓真实 SOME/IP/SOME/IP-SD 时，必须使用 `someipy` 后端并启动或连接 `someipyd`。

## 1. 安装

在仓库根目录执行：

```powershell
cd C:\code\someip
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,someipy]"
```

如果只做本地 GUI/单元测试，不需要真实协议栈，可以安装：

```powershell
python -m pip install -e ".[dev]"
```

## 2. 启动方式

### 2.1 Mock 模式

Mock 模式适合确认 GUI 功能、payload 编解码、日志和 trace，不会发真实网络报文。

```powershell
cd C:\code\someip
.\.venv\Scripts\Activate.ps1
python -m someip_gui_tool
```

### 2.2 真实 SOME/IP 模式

真实模式使用 `someipy` + `someipyd`，可通过 Wireshark 抓包验证 OfferService、FindService、SubscribeEventgroup 和 Event 报文。

先确认本机网卡 IP：

```powershell
Get-NetIPAddress -AddressFamily IPv4
```

选择实际接入 SOME/IP 网络的本机 IP。例如本机以太网是 `172.16.3.14`，则：

```powershell
cd C:\code\someip
.\.venv\Scripts\Activate.ps1

$env:SOMEIP_GUI_BACKEND='someipy'
$env:SOMEIP_GUI_START_DAEMON='1'
$env:SOMEIP_GUI_LOCAL_IP='172.16.3.14'
$env:SOMEIP_GUI_BASE_PORT='30500'

python -m someip_gui_tool
```

注意：`SOMEIP_GUI_LOCAL_IP` 必须是本机网卡 IP，不是对端 ECU IP。如果填错，常见现象是 GUI start 报 `Failed to connect to daemon after retries`，或者 Offer/Subscribe 端点声明错误。

## 3. 环境变量说明

| 变量 | 示例 | 作用 |
| --- | --- | --- |
| `SOMEIP_GUI_BACKEND` | `someipy` | 选择后端。默认 `mock` 不发真实报文；`someipy` 会连接真实 SOME/IP daemon。 |
| `SOMEIP_GUI_START_DAEMON` | `1` | 是否由 GUI 自动启动 `someipyd`。不设置时，需要用户提前手动启动 daemon。 |
| `SOMEIP_GUI_LOCAL_IP` | `172.16.3.14` | `someipyd` 绑定和声明 endpoint 的本机 IP。必须是本机网卡地址。 |
| `SOMEIP_GUI_BASE_PORT` | `30500` | `someipyd` TCP 控制端口和默认端口分配起点。 |

## 4. 启动前健康检查

建议真实模式启动 GUI 前先跑一次协议 spike：

```powershell
python scripts\run_protocol_spike.py --mode dry-run
python scripts\run_protocol_spike.py --mode real --local-ip 172.16.3.14 --base-port 30500 --start-daemon
```

期望看到：

- `someipy-api` PASS。
- `someipyd` PASS。
- UDP/TCP Event 场景 PASS。
- Field Getter/Notifier 场景 PASS。
- FF Method 可以显示 SKIP/LIMITED，当前不作为已支持能力。

Windows 下如果最后出现临时日志文件清理 `PermissionError`，但前面协议场景已经 PASS，通常是 `someipyd` 日志句柄释放较慢，不代表协议动作失败。

## 5. GUI 使用流程

### 5.1 导入服务定义

1. 启动 GUI。
2. 点击菜单中的导入/打开定义目录入口。
3. 选择 `C:\code\someip\ADC40_SOC`。
4. 左侧服务树会显示服务、Event、Method、Field。

常用测试服务：

| 服务 | Service ID | 用途 |
| --- | --- | --- |
| `ADASRouteSrv` | `0x080E` | UDP cycle event `VehicleInfo` |
| `CockpitIntellgntDecouplingSrv` | `0x080A` | TCP event `IntellgntSwtDecoupSts` |
| `IntelliDriveRmdSrv` | `0x080C` | Field getter/notifier `VertHeiRmdSts` |
| `SecondStartSrv` | `0x080D` | UDP event 和 FF method limited 检查 |
| `HUTSystemFunctions` | `0x0F01` | 多 TCP event/method fixture |

### 5.2 配置 Runtime Panel

选择服务后，在 Runtime Panel 配置：

| 配置项 | Server role 示例 | Client role 示例 |
| --- | --- | --- |
| Role | `Server` | `Client` |
| Local IP | 本机 IP，如 `172.16.3.14` | 本机 IP，如 `172.16.3.14` |
| Remote IP | 对端 ECU 或测试对端 IP | 对端 Server IP |
| Server Port | 服务端业务端口，如 `30520` | 对端 Server 端口 |
| Client Port | 对端 Client 端口 | 本机 Client 端口 |
| Multicast IP | `239.192.255.251` | `239.192.255.251` |

配置完成后点击 `Start`。

Server role 成功时，Run Log 应出现：

```text
Offered service ...
Started service ...
```

Client role 成功时，Run Log 应出现：

```text
Found service ...
Started service ...
```

如果 Client 没找到服务，会出现 `find_service_unavailable` warning。

### 5.3 发布 Event

Server role：

1. 先 Start 服务。
2. 在左侧选择 Event。
3. Operation 面板输入 Payload JSON。
4. 点击 `Publish Once`。
5. Cycle event 可点击 `Start Cycle` 和 `Stop Cycle`。

示例：`ADASRouteSrv.VehicleInfo`

```json
{"VehicleInfo":{"VehicleSpeed":12.5,"Odometer":99.25}}
```

期望 raw payload：

```text
4148000042c68000
```

Client role：

1. 先 Start 服务。
2. 选择同一 Event。
3. 点击 `Subscribe`。
4. 收到事件后 Message Trace 会出现 RX Event。
5. 不需要接收时点击 `Unsubscribe`。

### 5.4 Field Getter/Notifier

Field Getter 用于 Client role：

1. Client Start 服务。
2. 选择 Field `VertHeiRmdSts`。
3. 点击 `Get`。
4. Run Log 显示 getter result，Message Trace 显示 TX/RX。

注意：按 AUTOSAR SOME/IP 标准，Field Getter request 通常应为空 payload，字段值应在 response payload 中返回。当前 MVP-1 实现会把 GUI 中的 getter payload 编码后发出，需要用 Wireshark 抓包确认是否符合项目要求。

Field Notifier 用于 Server role：

1. Server Start 服务。
2. 选择 Field `VertHeiRmdSts`。
3. 输入：

```json
{"VertHeiRmdSts":1}
```

4. 点击 `Notify`。

### 5.5 Method

当前 MVP-1 中 Fire-and-Forget method 显示为 `limited`。例如 `SecondStartSrv.SecondStartCtrl`：

```json
{"SecondStartCtrlCmd":1}
```

GUI 可以记录 limited 状态，但不能把它作为已通过的标准 SOME/IP FF Method 支持能力。RR Method 和 Field Setter 当前仍为 gated/unsupported。

## 6. Wireshark 抓包

真实模式下，建议先看 SOME/IP-SD：

```text
udp.port == 30490
```

OfferService 期望：

- Destination: `239.192.255.251`
- UDP destination port: `30490`
- SOME/IP Message ID: `0xFFFF8100`
- SD Entry Type: `OfferService`
- Service ID: 被测服务 ID，如 `0x080E`
- Instance ID: `0x0001`
- TTL: 大于 `0`

业务报文可按端口过滤：

```text
udp.port == <server_port> || tcp.port == <server_port>
```

如果 Wireshark 只显示 UDP，没有显示 SOME/IP：

1. 先确认 `udp.port == 30490` 是否有包。
2. 如果业务端口有 UDP/TCP 内容，可右键报文选择 `Decode As...`，手动指定 SOME/IP。
3. 如果完全没有 `30490`，说明还没有发出标准 SOME/IP-SD Offer/Find，需要先检查 backend、daemon、local IP 和 Start 状态。

## 7. 日志和证据导出

GUI 支持导出：

- Message Trace CSV
- Message Trace JSON
- Run Log TXT
- Run Log JSON

建议每次实车/台架验证保存：

1. Wireshark `.pcapng`。
2. GUI Message Trace。
3. GUI Run Log。
4. 测试时使用的服务、角色、IP、端口配置。

## 8. 常见问题

### Start 后报 Failed to connect to daemon after retries

排查：

1. 是否设置 `SOMEIP_GUI_BACKEND='someipy'`。
2. 是否设置 `SOMEIP_GUI_START_DAEMON='1'`，或已手动启动 `someipyd`。
3. `SOMEIP_GUI_LOCAL_IP` 是否为本机真实网卡 IP。
4. `SOMEIP_GUI_BASE_PORT` 是否被占用。

检查端口：

```powershell
Get-NetTCPConnection -LocalPort 30500 -ErrorAction SilentlyContinue
```

### Wireshark 没有 SOME/IP

排查：

1. GUI 是否使用 `someipy` 后端，而不是默认 `mock`。
2. 服务是否 Start 成功。
3. 是否有 `udp.port == 30490`。
4. 是否抓错网卡。
5. 业务端口是否需要手动 `Decode As...` SOME/IP。

### spike 里 endpoint_ip 是 172.16.3.14，是否正常

如果 `172.16.3.14` 是本机以太网 IP，就是正常的。SOME/IP daemon 需要声明本机 endpoint，不能声明对端 ECU IP。

## 9. 标准符合性验证

启动和基本使用确认后，按下面文档做标准级验收：

- `docs/mvp1-autosar-someip-compliance-verification.md`
- `docs/mvp1-gui-real-someip-manual-verification.md`

其中 AUTOSAR 符合性文档要求以 Wireshark 抓包为最终判据，GUI Run Log 和 Message Trace 只作为辅助证据。

