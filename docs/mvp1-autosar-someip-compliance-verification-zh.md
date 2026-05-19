# MVP-1 AUTOSAR SOME/IP 标准符合性验证

日期：2026-05-18

本文档用于对当前 MVP-1 已实现能力做标准符合性验证。目标不是证明 GUI 能点通，而是用 AUTOSAR SOME/IP 与 SOME/IP-SD 的报文字段、入口类型、TTL、版本、端点、传输层和载荷规则，验证当前实现是否真的符合协议。

结论口径：GUI Run Log、Message Trace 和导出文件只能作为辅助证据；最终判定必须以抓包或对端 ECU 实际报文为准。

## 1. 标准依据

| 标准资料 | 本文使用范围 |
| --- | --- |
| [AUTOSAR R24-11 SOME/IP Protocol Specification](https://www.autosar.org/fileadmin/standards/R24-11/FO/AUTOSAR_FO_PRS_SOMEIPProtocol.pdf) | SOME/IP Header、Message ID、Method/Event ID、Length、Request ID、Protocol Version、Interface Version、Message Type、Return Code、Field getter/notifier、事件与方法语义 |
| [AUTOSAR R20-11 SOME/IP Service Discovery Protocol Specification](https://www.autosar.org/fileadmin/standards/R20-11/FO/AUTOSAR_PRS_SOMEIPServiceDiscoveryProtocol.pdf) | SOME/IP-SD Header、SD Service ID/Method ID、FindService、OfferService、StopOfferService、SubscribeEventgroup、StopSubscribeEventgroup、SubscribeEventgroupAck/Nack、SD 端口与端点选项 |

若项目指定其他 AUTOSAR release，需把本文的标准引用版本替换为项目要求版本，再重新确认字段和 requirement ID。

## 2. 判定状态

| 状态 | 含义 |
| --- | --- |
| PASS | 抓包与 GUI 证据均满足标准要求 |
| FAIL | 抓包证据违反标准要求，或 GUI 声称支持但未发出符合标准的协议报文 |
| NEEDS_CAPTURE | 代码路径存在，但必须抓包确认 backend 实际报文 |
| LIMITED | 当前实现明确标记为受限，不应作为标准支持能力通过 |
| GATED | 当前 MVP-1 未开放或缺少 fixture/backend 支撑，不纳入通过范围 |
| N/A | 不属于当前 MVP-1 范围 |

## 3. 当前实现范围

| 功能 | 当前实现入口 | MVP-1 状态 | 标准符合性预判 |
| --- | --- | --- | --- |
| Server Start -> OfferService | `RuntimeSession.start_service()` -> `SomeipyAdapter.offer_service()` -> `ServerServiceInstance.start_offer()` | 已实现 | NEEDS_CAPTURE |
| Stop Service -> StopOfferService | `RuntimeSession.stop_service()` -> `SomeipyAdapter.stop_service()` -> `ServerServiceInstance.stop_offer()` | 已实现 | NEEDS_CAPTURE |
| Client Start -> FindService/availability | `RuntimeSession.start_service()` -> `SomeipyAdapter.find_service()` -> `ClientServiceInstance.is_available()` | 已实现 | NEEDS_CAPTURE。GUI 的 Found 只证明 backend 可用，不证明 FindService 报文格式 |
| Subscribe Eventgroup | `RuntimeSession.subscribe_event()` -> `SomeipyAdapter.subscribe_eventgroup()` | 已实现 | NEEDS_CAPTURE |
| Unsubscribe Eventgroup | `RuntimeSession.unsubscribe_event()` -> `SomeipyAdapter.unsubscribe_eventgroup()` | 已实现 | NEEDS_CAPTURE |
| UDP/TCP Event publish/receive | `publish_event()`、event callback trace | 已实现 | NEEDS_CAPTURE |
| Field getter | `RuntimeSession.field_get()` -> `SomeipyAdapter.field_get()` | 已实现 | 高风险：标准要求 getter request 空载荷，当前实现会编码 GUI 输入值 |
| Field notifier | `RuntimeSession.field_notify()` -> `SomeipyAdapter.field_notify()` | 已实现 | NEEDS_CAPTURE；`0x9001` notifier ID 需确认是否符合项目 ID 分配规则 |
| FF Method | `SomeipyAdapter.call_method()` 对 FF 返回 `limited` | LIMITED | 不能作为 FF method 标准支持通过 |
| RR Method | backend capability 标记 unsupported/gated | GATED | N/A |
| Field setter | fixture 无 setter 或 adapter 未实现 | GATED | N/A |

## 4. 待验证服务与报文期望

默认基于 `ADC40_SOC/*.json`，实例 ID 均为 `0x0001`，Major Version 为 `1`，Minor Version 为 `0`，SD multicast IP 为 `239.192.255.251`，Offer/Find TTL 为 `3s`。

| 服务 | 元素 | 标准期望 Message ID | L4 | Eventgroup | 载荷示例 |
| --- | --- | --- | --- | --- | --- |
| `ADASRouteSrv` `0x080E` | Event `VehicleInfo` `0x8001` | `0x080E8001` | UDP | `0x0001` | `{"VehicleInfo":{"VehicleSpeed":12.5,"Odometer":99.25}}` -> `4148000042c68000` |
| `CockpitIntellgntDecouplingSrv` `0x080A` | Event `IntellgntSwtDecoupSts` `0x8001` | `0x080A8001` | TCP | `0x0001` | 三个 `uint8` 示例 -> `010203` |
| `IntelliDriveRmdSrv` `0x080C` | Field Getter `VertHeiRmdSts` `0x1001` | `0x080C1001` | TCP | N/A | 标准 request 应为空；response 示例 `01` |
| `IntelliDriveRmdSrv` `0x080C` | Field Notifier `VertHeiRmdSts` `0x9001` | `0x080C9001` | TCP | `0x0001` | `{"VertHeiRmdSts":1}` -> `01` |
| `SecondStartSrv` `0x080D` | Event `SecondStartPopup` `0x8001` | `0x080D8001` | UDP | `0x0001` | `{"SecondStartPopup":1}` -> `01` |
| `SecondStartSrv` `0x080D` | FF Method `SecondStartCtrl` `0x0001` | `0x080D0001` | UDP | N/A | `{"SecondStartCtrlCmd":1}` -> `01`，当前 LIMITED |
| `HUTSystemFunctions` `0x0F01` | TCP Events `0x8001..0x8004` | `0x0F018001..0x0F018004` | TCP | `0x0001..0x0004` | 按 fixture 参数编码 |

注意：AUTOSAR SOME/IP 推荐 Method ID 空间中 method 使用 `0x0000..0x7FFF`，events/notifications 使用 `0x8000..0x8FFF`。当前 `0x080C` 的 field notifier 为 `0x9001`，高位仍表示事件类元素，但超出推荐的 `0x8FFF` 上限。若项目规范把该推荐升级为强制规则，则此项应记录为偏差；若 OEM/系统设计明确允许，则可放行。

## 5. 全局协议验收要求

### 5.1 SOME/IP Header

所有非 SD 的 SOME/IP 方法、事件、字段报文均需满足：

| Req ID | 标准检查点 | 抓包通过判据 |
| --- | --- | --- |
| SOMEIP-HDR-001 | Message ID 为 32 bit，由 Service ID 和 Method/Event ID 组成 | 例如 `0x080E8001` 应解码为 Service ID `0x080E`、Method/Event ID `0x8001` |
| SOMEIP-HDR-002 | Length 从 Request ID 开始算到报文结束 | `Length == 8 + payload_length`，TP 分片不在 MVP-1 范围 |
| SOMEIP-HDR-003 | Protocol Version | `0x01` |
| SOMEIP-HDR-004 | Interface Version | 应等于服务 Major Version，当前 fixture 期望 `0x01` |
| SOMEIP-HDR-005 | Message Type | Request `0x00`、RequestNoReturn `0x01`、Notification `0x02`、Response `0x80`、Error `0x81` |
| SOMEIP-HDR-006 | Return Code | 非 Response/Error 应为 `0x00`；成功 Response 应为 `E_OK` `0x00` |
| SOMEIP-HDR-007 | Request ID | RR getter/request 的 response 必须复制 request 的 Request ID |
| SOMEIP-HDR-008 | 传输层 | UDP/TCP 必须与 fixture 的 `L4-Protocol` 一致 |

### 5.2 SOME/IP-SD Header 与入口

| Req ID | 标准检查点 | 抓包通过判据 |
| --- | --- | --- |
| SD-HDR-001 | SD 报文使用 SOME/IP Header | Message ID 必须为 `0xFFFF8100` |
| SD-HDR-002 | SD Message Type/Return Code | Message Type `0x02`，Return Code `0x00` |
| SD-HDR-003 | SD 端口与 multicast | SD 报文通过 UDP `30490`，multicast 使用 `239.192.255.251`，除非项目配置另有定义 |
| SD-FIND-001 | FindService Entry | Type `0x00`，Service ID/Instance ID/Major/Minor/TTL 符合服务查找语义；TTL 不能为 `0` |
| SD-OFFER-001 | OfferService Entry | Type `0x01`，Service ID/Instance ID/Major/Minor/TTL 与 fixture 一致；TTL > `0` |
| SD-OFFER-002 | Offer endpoint options | Offer 必须引用 IPv4/IPv6 Endpoint Option，IP/Port/L4 与 GUI runtime 配置一致 |
| SD-STOPOFFER-001 | StopOfferService Entry | 入口字段同 OfferService，但 TTL 为 `0x000000` |
| SD-SUB-001 | SubscribeEventgroup Entry | Type `0x06`，Service ID/Instance ID/Major/Eventgroup ID/TTL 与订阅目标一致 |
| SD-SUB-002 | Subscribe Ack/Nack | Ack/Nack Type `0x07`；Ack TTL 与订阅一致，Nack TTL 为 `0` |
| SD-SUB-003 | StopSubscribeEventgroup Entry | 字段同 SubscribeEventgroup，但 TTL 为 `0x000000` |

## 6. 测试准备

### 6.1 环境

1. Windows x64，Python venv 已安装项目依赖。
2. 安装 real backend：`python -m pip install -e ".[dev,someipy]"`。
3. 安装 Wireshark 或等价抓包工具，并启用 SOME/IP、SOME/IP-SD dissector。
4. 准备两种验证拓扑之一：
   - 本机 loopback：两个 GUI 实例或 spike/对端脚本，一端 Server，一端 Client。
   - 实车/台架：GUI 与真实 ECU 处于同一 VLAN/IP 网段，端口和 multicast 路由可达。

### 6.2 启动配置

推荐先运行自动化健康检查，确认 backend 能启动：

```powershell
python -m pytest
python scripts\run_protocol_spike.py --mode dry-run
python scripts\run_protocol_spike.py --mode real --start-daemon
```

GUI real backend 启动示例：

```powershell
$env:SOMEIP_GUI_BACKEND='someipy'
$env:SOMEIP_GUI_LOCAL_IP='127.0.0.1'
$env:SOMEIP_GUI_BASE_PORT='30500'
$env:SOMEIP_GUI_START_DAEMON='1'
python -m someip_gui_tool
```

实车/台架验证时，`SOMEIP_GUI_LOCAL_IP` 应改为本机真实网卡 IP；GUI Runtime Panel 中的 local/remote/server/client port 必须与测试拓扑一致。

### 6.3 抓包建议

常用 Wireshark display filter：

```text
someip || someipsd
udp.port == 30490
udp.port == <server_port> || tcp.port == <server_port>
ip.addr == <local_ip> && (someip || someipsd)
```

若 Wireshark 字段名随版本不同，不强依赖 display filter 字段名；以报文解码树中显示的 SOME/IP Header、SOME/IP-SD Entries 和 Options 为准。

## 7. 标准符合性测试用例

### STD-00 基线健康检查

目的：确认测试环境不是 backend 或依赖问题。

步骤：
1. 运行 `python -m pytest`。
2. 运行 `python scripts\run_protocol_spike.py --mode dry-run`。
3. 若使用 real backend，运行 `python scripts\run_protocol_spike.py --mode real --start-daemon`。

通过判据：
- 单元测试通过。
- dry-run 全部通过。
- real spike 中 `someipy-api`、`someipyd`、UDP/TCP event、field getter/notifier 支持路径通过。
- FF method 可以是 SKIP/LIMITED，但不能被记录为标准 PASS。

### SD-01 Server Start 发送 OfferService

目的：验证当前实现的 `offer_service` 符合 SOME/IP-SD OfferService。

前置：
- 选择 `ADASRouteSrv` `0x080E` 或 `CockpitIntellgntDecouplingSrv` `0x080A`。
- GUI 角色为 Server。
- 抓包已开始。

GUI 步骤：
1. 导入 `ADC40_SOC`。
2. 选择目标服务。
3. Runtime Panel 设置 Server role、local IP、remote IP、server port、client port、multicast IP。
4. 点击 Start。

抓包通过判据：
- 出现 SOME/IP-SD 报文，Message ID `0xFFFF8100`。
- Entry Type 为 `0x01` OfferService。
- Service ID 等于被测服务，如 `0x080E`。
- Instance ID `0x0001`。
- Major `0x01`，Minor `0x00000000`。
- TTL 为 `3` 或 GUI/runtime 配置值，且大于 `0`。
- Endpoint Option 包含 GUI server endpoint IP/Port，L4 与该服务需要的 UDP/TCP 一致。
- SD 报文使用 UDP `30490`。

GUI 辅助证据：
- Run Log 包含 `Offered service ...`。
- Problems 无 start/offer error。

失败判据：
- 未出现 OfferService。
- OfferService 中 Service ID、Instance ID、版本、TTL、endpoint 任一错误。
- GUI 显示已启动，但抓包没有标准 SD Offer。

### SD-02 Stop Service 发送 StopOfferService

目的：验证停止服务时发出标准 StopOfferService。

前置：SD-01 已通过，服务处于 Server running。

GUI 步骤：
1. 点击 Stop。
2. 继续抓包至少 2 秒。

抓包通过判据：
- 出现 StopOfferService，Entry 字段与 SD-01 的 OfferService 对应。
- TTL 为 `0x000000`。
- 停止后不再继续周期性 Offer 同一服务。

GUI 辅助证据：
- Run Log 包含 `Stopped service ...`。

失败判据：
- Stop 后只关闭 GUI 状态，没有 StopOffer 报文。
- StopOffer TTL 非 0。
- Stop 后仍持续 Offer 同一服务。

### SD-03 Client Start 发送/接收 FindService 并发现服务

目的：验证当前实现的 `find_service` 不只是 GUI polling，而是符合 SOME/IP-SD FindService/Offer 发现语义。

前置：
- 对端 Server 已按 SD-01 Offer 同一服务。
- 当前 GUI 实例为 Client role。
- 抓包已开始。

GUI 步骤：
1. 选择同一服务。
2. 设置 Client role、local/remote IP、server/client port、multicast IP。
3. 点击 Start。

抓包通过判据：
- 若 client 未持有有效 Offer，应出现 FindService Entry Type `0x00`。
- FindService 的 Service ID 与目标服务一致；Instance ID 可为 `0x0001` 或按标准使用 `0xFFFF` 查询全部实例；Major/Minor 可为具体值或 any 值。
- Find TTL 大于 `0`。
- client 收到匹配的 OfferService，Service ID/Instance ID/Major/Minor 与目标服务一致。
- GUI 的 Found 状态必须能与抓包中的 Find/Offer 或有效 Offer cache 对应。

GUI 辅助证据：
- Run Log 包含 `Found service ...`。
- 若没有对端 Offer，Run Log 应出现 `find_service_unavailable` warning，而不是假成功。

失败判据：
- GUI 显示 Found，但抓包既无 Find，也无有效 Offer。
- FindService entry 带了不允许的 Endpoint/Multicast Option。
- Find TTL 为 0。

### SD-04 SubscribeEventgroup

目的：验证事件订阅符合 SOME/IP-SD SubscribeEventgroup。

前置：
- Server 正在 Offer 被测服务。
- Client 已 Found 服务。
- 推荐使用 `ADASRouteSrv.VehicleInfo` `0x080E/0x8001` eventgroup `0x0001`。

GUI 步骤：
1. Client 选择事件 `VehicleInfo`。
2. 点击 Subscribe。

抓包通过判据：
- 出现 SubscribeEventgroup Entry Type `0x06`。
- Service ID `0x080E`，Instance ID `0x0001`，Major `0x01`。
- Eventgroup ID `0x0001`。
- TTL 为 `3` 或 runtime find/subscription TTL，且大于 `0`。
- Endpoint Option 包含 client endpoint IP/Port。
- Server 返回 SubscribeEventgroupAck Type `0x07`，字段匹配原 Subscribe；如返回 Nack，则 TTL 应为 `0` 且需记录失败原因。

GUI 辅助证据：
- Run Log 包含 `Requested subscription for eventgroup 0x0001 ...`，仅表示 GUI 已发出请求，不作为协议通过判据。

失败判据：
- GUI 已提交订阅请求但无 SubscribeEventgroup 报文。
- Subscribe eventgroup ID 错误。
- ACK/NACK 与 Subscribe 字段不匹配。

### SD-05 StopSubscribeEventgroup

目的：验证取消订阅符合 StopSubscribeEventgroup。

前置：SD-04 已订阅成功。

GUI 步骤：
1. Client 选择同一事件。
2. 点击 Unsubscribe。
3. Server 再 Publish 一次该事件。

抓包通过判据：
- active subscription 已建立时，出现 StopSubscribeEventgroup，字段与原 Subscribe 对应，TTL 为 `0x000000`。
- 取消订阅后，Client 不应再接收该 eventgroup 的事件通知；若仍收到，需要确认是否是发送前已排队或另有订阅者。

GUI 辅助证据：
- Run Log 包含 `Requested unsubscribe for eventgroup ...`，仅表示 GUI 已发出请求，不作为协议通过判据。
- Message Trace 中 unsubscribe 后无新的 RX Event。

失败判据：
- active subscription 已建立时，Unsubscribe 未产生 TTL 0 的 StopSubscribe。
- Client 仍稳定接收后续事件。

### EVT-UDP-01 UDP Event Notification

目的：验证 UDP event 发布符合 SOME/IP event notification。

前置：
- 使用 `ADASRouteSrv.VehicleInfo`。
- Client 已订阅 eventgroup `0x0001`。
- Server role GUI 选择同一事件。

GUI 步骤：
1. Payload 输入：

```json
{"VehicleInfo":{"VehicleSpeed":12.5,"Odometer":99.25}}
```

2. 点击 Publish Once。

抓包通过判据：
- 出现 SOME/IP Message ID `0x080E8001`。
- Message Type 为 Notification `0x02`。
- Return Code 为 `0x00`。
- Protocol Version `0x01`，Interface Version `0x01`。
- Length 为 `16`，即 `8 + 8 bytes payload`。
- Payload hex 为 `4148000042c68000`。
- L4 为 UDP，endpoint 与 OfferService Endpoint Option 一致。

GUI 辅助证据：
- Server Message Trace 有 TX Event，raw payload `4148000042c68000`。
- Client Message Trace 有 RX Event，decoded payload 与输入一致。

失败判据：
- Message ID、Message Type、Length、payload、L4 任一不符。
- 仅 GUI 记录 TX，但 client 抓包/RX trace 未收到。

### EVT-TCP-01 TCP Event Notification

目的：验证 TCP event 发布符合 SOME/IP event notification。

前置：
- 使用 `CockpitIntellgntDecouplingSrv.IntellgntSwtDecoupSts`，service `0x080A`，event `0x8001`，eventgroup `0x0001`。
- Client 已订阅。

GUI 步骤：
1. 输入 fixture 参数对应的三个 `uint8` 值，期望 raw payload `010203`。
2. 点击 Publish Once。

抓包通过判据：
- TCP 连接建立在 client/server endpoint 之间。
- SOME/IP Message ID `0x080A8001`。
- Message Type Notification `0x02`。
- Length 为 `11`，即 `8 + 3 bytes payload`。
- Payload hex 为 `010203`。
- 报文通过 TCP，而不是 UDP。

失败判据：
- 使用了错误传输层。
- TCP event 在未建立 TCP endpoint/订阅关系时仍被 GUI 标记成功。

### FIELD-GET-01 Field Getter Request/Response

目的：验证 field getter 是否符合 AUTOSAR SOME/IP field getter 语义。

标准期望：
- Field getter 是 request/response 调用。
- Getter request payload 应为空。
- Getter response payload 携带字段值。

前置：
- 使用 `IntelliDriveRmdSrv.VertHeiRmdSts`，service `0x080C`，getter `0x1001`，TCP。
- Server role 对端已启动并 Offer。
- Client role GUI 已 Found 服务。

GUI 步骤：
1. 选择 field `VertHeiRmdSts`。
2. 观察 Payload JSON。当前 GUI 会显示 getter 参数，这是本测试的重点风险。
3. 点击 Get。

抓包通过判据：
- Client -> Server SOME/IP Request，Message ID `0x080C1001`。
- Message Type Request `0x00`。
- Request Length 为 `8`，即空 payload。
- Server -> Client SOME/IP Response，Message ID `0x080C1001`。
- Response Message Type `0x80`，Return Code `0x00`。
- Response Request ID 与 request 完全一致。
- Response payload 为字段值，例如 `01`。

当前实现风险：
- `RuntimeSession.field_get()` 会对 `field.getter.parameters` 编码；`OperationPanel.show_field()` 在 Client role 会把 getter 参数放入 Payload JSON。
- 如果抓包中 getter request payload 为 `01` 或其他非空值，则 FIELD-GET-01 判定 FAIL，即使 GUI Run Log 显示 `result=success`。

失败判据：
- Getter request 非空 payload。
- Response 未复制 Request ID。
- Response Return Code 非 `E_OK` 且 GUI 未报错。

### FIELD-NOTIFY-01 Field Notifier Notification

目的：验证 field notifier 作为 event notification 发送字段值。

前置：
- 使用 `IntelliDriveRmdSrv.VertHeiRmdSts` notifier `0x9001`，eventgroup `0x0001`，TCP。
- Client 已 Subscribe eventgroup `0x0001`。

GUI 步骤：
1. Server role 选择 field `VertHeiRmdSts`。
2. Payload 输入：

```json
{"VertHeiRmdSts":1}
```

3. 点击 Notify。

抓包通过判据：
- SOME/IP Message ID `0x080C9001`。
- Message Type Notification `0x02`。
- Payload `01`。
- 通过 TCP。
- Client RX trace 解码为 `{"VertHeiRmdSts":1}`。

附加检查：
- 若项目强制 event/notifier ID 必须在 `0x8000..0x8FFF`，则 `0x9001` 需要作为 ID 分配偏差记录。

失败判据：
- Notifier 未走 eventgroup 订阅路径。
- 未订阅时仍稳定收到 notifier。
- Message ID 或 L4 错误。

### METHOD-FF-01 Fire-and-Forget Method

目的：确认当前实现不会误把 FF method 声称为标准已支持。

前置：
- 使用 `SecondStartSrv.SecondStartCtrl`，service `0x080D`，method `0x0001`，UDP，RR/FF 为 `FF`。

标准期望：
- 应发出 SOME/IP RequestNoReturn，Message Type `0x01`。
- Message ID `0x080D0001`。
- 不应期待 response。
- 若接收方错误处理，也不应按 RR 方法返回普通 response。

GUI 步骤：
1. Client role 选择 method `SecondStartCtrl`。
2. 输入：

```json
{"SecondStartCtrlCmd":1}
```

3. 点击 Call。

当前 MVP-1 预期：
- GUI 应明确显示 fire-and-forget method execution is limited。
- Run Log/Trace 可记录 `limited`。
- 不得把此项记为协议 PASS。

抓包判定：
- 若没有 `0x080D0001` RequestNoReturn 报文：结果为 LIMITED，不是 PASS。
- 若出现 RequestNoReturn 且字段全部符合标准，可记录为 OBSERVED，但在代码移除 limited gate 前仍不能作为产品能力 PASS。

失败判据：
- GUI 显示 success，但实际未发 RequestNoReturn。
- 发成 Request `0x00` 或等待 Response。

### ID-01 Message ID 与元素 ID 分配检查

目的：验证服务和元素 ID 组合符合 SOME/IP Message ID 规则。

检查方法：
1. 对每个已实现操作抓包。
2. 对照第 4 节表格检查 Message ID。
3. 确认 Service ID 高 16 bit，Method/Event ID 低 16 bit。

通过判据：
- 所有 Message ID 与 fixture 一致。
- methods/getters 使用低位 method ID。
- events/notifiers 使用事件类 ID；`0x9001` 的项目规则已被确认。

失败判据：
- Service ID/Element ID 拼接错误。
- 事件被错误发送为 method ID，或 method 被错误发送为 event notification。

### SER-01 载荷序列化检查

目的：验证 payload codec 与 SOME/IP 线序一致。

当前 codec 期望：
- `uint8` -> 1 byte。
- `uint64` -> big-endian。
- `float32` -> big-endian IEEE 754。
- Struct 按 member `Position` 顺序拼接。
- 固定数组按元素顺序拼接。

抓包通过判据：
- `VehicleSpeed=12.5` -> `41480000`。
- `Odometer=99.25` -> `42c68000`。
- `VehicleInfo` 合并 payload -> `4148000042c68000`。
- `VertHeiRmdSts=1` -> `01`。
- 抓包 payload 与 GUI Message Trace raw payload 一致。

失败判据：
- 字节序错误。
- Struct member 顺序错误。
- GUI trace raw payload 与实际 packet payload 不一致。

## 8. 结果记录模板

### 8.1 测试执行记录

| Test ID | 服务/元素 | GUI 结果 | 抓包结果 | 判定 | 证据文件 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| SD-01 | | | | | | |
| SD-02 | | | | | | |
| SD-03 | | | | | | |
| SD-04 | | | | | | |
| SD-05 | | | | | | |
| EVT-UDP-01 | | | | | | |
| EVT-TCP-01 | | | | | | |
| FIELD-GET-01 | | | | | | |
| FIELD-NOTIFY-01 | | | | | | |
| METHOD-FF-01 | | | | | | |
| ID-01 | | | | | | |
| SER-01 | | | | | | |

### 8.2 抓包证据记录

| Packet No. | Time | Direction | Message ID | Entry/Message Type | Service ID | Element/Eventgroup ID | TTL | L4 | Endpoint | Payload Hex | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | | | | |

### 8.3 缺陷记录模板

| Defect ID | Test ID | 标准要求 | 实际行为 | 影响 | 建议修复 |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## 9. MVP-1 标准符合性 Gate

MVP-1 可声明"当前已实现功能符合 SOME/IP 标准"的最低条件：

1. SD-01、SD-02、SD-03、SD-04、SD-05 全部 PASS。
2. EVT-UDP-01 与 EVT-TCP-01 全部 PASS。
3. FIELD-NOTIFY-01 PASS。
4. SER-01 PASS。
5. FIELD-GET-01 必须 PASS；如果 getter request 非空，则当前 field getter 不能声明标准符合。
6. METHOD-FF-01 只能标记 LIMITED；不能作为 MVP-1 标准通过项。
7. 所有 PASS 项必须有 `.pcapng`、GUI trace export 或 run log 截图/导出作为证据。

当前代码阅读后的重点风险：

| 风险 | 原因 | 处理建议 |
| --- | --- | --- |
| Field getter request 可能非标准 | 当前 GUI 和 Runtime 会编码 getter 参数作为 request payload | 抓包确认；若非空，应调整 getter call 使用空 payload，并把字段值只用于 server response/mock response |
| FindService 报文不可仅凭 GUI Found 判定 | adapter 通过 `is_available()` polling 隐藏 SD 细节 | 必须抓包确认 Find/Offer 或有效 Offer cache |
| Offer/Subscribe 依赖 `someipy` 实际报文 | 当前代码调用 backend API，未自行构造 SD packet | 必须抓包确认 entry type、TTL、endpoint option |
| FF method 不可作为已支持 | adapter 对 FF method 返回 `limited`，不发送可证明的 FF request | 保持 LIMITED，后续 backend 决策后再验收 |
| Field notifier ID `0x9001` 可能与推荐范围不一致 | AUTOSAR 推荐 events/notifications 使用 `0x8000..0x8FFF` | 与项目 ID 分配规范确认；必要时登记偏差 |
