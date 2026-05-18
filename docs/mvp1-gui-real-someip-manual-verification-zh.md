# MVP-1 GUI 真实 SOME/IP 手动验证

日期：2026-05-18

## 1. 目的

本文档定义了当前 MVP-1 已实现功能集的手动 GUI 验证流程。目标是证明 GUI 能够通过应用程序适配器边界驱动真实 SOME/IP 后端，并且支持的协议路径能够产生可观察的运行日志、消息追踪和导出证据。

本文档有意限定在已实现的 MVP-1 行为范围内。MVP-2 功能（如结构化载荷表单、原始十六进制模式、项目文件、搜索/过滤、最近会话和动作序列）不属于本次手动验证的范围。

## 2. 当前支持边界

MVP-1 GUI/手动验证支持的功能：

- 打开 `ADC40_SOC` 服务定义目录。
- 解析服务、方法、事件、字段、数据类型和部署数据。
- 为每个服务选择 Client 或 Server 角色。
- 配置运行时 IP、服务器端口、客户端端口和组播 IP。
- 启动和停止服务。
- Client 角色：启动时查找服务，订阅/取消订阅事件，调用支持的方法路径，字段 getter。
- Server 角色：启动时提供服务，单次发布事件，启动/停止周期事件，字段 notifier。
- 运行日志、消息追踪、问题面板。
- 将运行日志导出为 TXT/JSON，消息追踪导出为 CSV/JSON。
- 通过环境变量使用真实 `someipy` 后端。
- 打包应用启动/关闭冒烟测试（`--smoke-exit`）。

已知受限/门控行为：

- FF 方法报告 `limited`；不被视为经过验证的端到端请求处理。
- RR 方法保持门控状态，直到有经过验证的测试夹具和适配器路径。
- Field setter 保持门控或不可用，直到有受支持的测试夹具/后端路径。
- VLAN 和防火墙不会自动配置。

## 3. 测试环境

测试前记录以下信息：

| 项目 | 值 |
| --- | --- |
| 测试人员 | |
| 日期/时间 | |
| 机器名称 | |
| Windows 版本 | |
| Python 版本 | |
| Git 提交 | |
| 应用类型 | 源码 / PyInstaller exe |
| 后端 | `someipy` |
| GUI 使用的本地 IP | |
| 对端 IP 或回环 | |
| 服务器端口 | |
| 客户端端口 | |
| 组播 IP | |
| Wireshark 抓包文件 | |

推荐的本地回环端口：

- 守护进程 TCP 控制端口：`30500`
- 服务服务器端口：`32000`
- 服务客户端端口：`32001`
- 组播 IP：`239.192.255.251`

对外部对端设备测试，请将 IP 和端口值替换为目标网络配置。

## 4. 预检

### PF-01 安装与后端可用性

步骤：

1. 在仓库根目录打开 PowerShell。
2. 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

3. 如果尚未安装真实后端依赖：

```powershell
python -m pip install -e ".[dev,someipy]"
```

4. 运行单元测试和干运行协议检查：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest
python scripts\run_protocol_spike.py --mode dry-run
```

预期结果：

- Pytest 通过。
- 干运行报告以下项目 PASS：
  - `udp-ff-method`
  - `tcp-method`
  - `udp-event`
  - `tcp-event`
  - `field-getter-notifier`

结果：

- 通过 / 失败：
- 备注：

### PF-02 真实后端回环健康检查

步骤：

1. 运行：

```powershell
python scripts\run_protocol_spike.py --mode real --start-daemon
```

预期结果：

- `someipy-api` PASS。
- `someipyd` PASS。
- `udp-event` PASS。
- `tcp-event` PASS。
- `field-getter-notifier` PASS。
- `udp-ff-method` 和 `tcp-method` 可能为 SKIP，附带 FF 限制说明。

结果：

- 通过 / 失败：
- 备注：

此检查用于在 GUI 测试开始前确认机器能够运行真实的 `someipy` 协议栈。

## 5. 使用真实后端启动 GUI

### GUI-00 源码启动

步骤：

1. 在 PowerShell 中：

```powershell
$env:SOMEIP_GUI_BACKEND='someipy'
$env:SOMEIP_GUI_LOCAL_IP='127.0.0.1'
$env:SOMEIP_GUI_BASE_PORT='30500'
$env:SOMEIP_GUI_START_DAEMON='1'
python -m someip_gui_tool
```

2. 确认窗口打开。

预期结果：

- 窗口标题为 `SOME/IP Test Tool`。
- 无启动崩溃。
- 状态栏显示就绪/正常状态。

结果：

- 通过 / 失败：
- 备注：

### GUI-01 打包启动冒烟测试

步骤：

1. 如需构建打包：

```powershell
python -m PyInstaller packaging\pyinstaller\someip-gui-tool.spec
```

2. 运行冒烟测试：

```powershell
dist\someip-gui-tool.exe --smoke-exit
```

预期结果：

- 进程退出码为 0。

结果：

- 通过 / 失败：
- 备注：

## 6. 定义导入与运行时配置

### GUI-10 打开服务定义

步骤：

1. 在 GUI 中选择 `File -> Open Definition Directory...`。
2. 选择：

```text
C:\code\someip\ADC40_SOC
```

预期结果：

- 服务树加载 5 个服务。
- 服务节点包含 ID：`0x080A`、`0x080C`、`0x080D`、`0x080E`、`0x0F01`。
- Method、Event 和 Field 子节点可见。
- 运行日志包含已加载定义的消息。
- 问题面板无导入失败。

结果：

- 通过 / 失败：
- 备注：

### GUI-11 运行时验证拒绝缺失端口

步骤：

1. 选择任意服务节点。
2. 将 Server Port 和 Client Port 留空。
3. 点击 `Start`。

预期结果：

- 服务不启动。
- 问题面板包含 `server_port_missing` 和 `client_port_missing`。
- 运行日志记录验证错误。

结果：

- 通过 / 失败：
- 备注：

### GUI-12 运行时配置接受有效回环端口

步骤：

1. 选择服务 `0x080E`。
2. 将 Role 设为 `Server`。
3. 将 Local IP 设为 `127.0.0.1`。
4. 将 Remote IP 设为 `127.0.0.1`。
5. 将 Server Port 设为 `32000`。
6. 将 Client Port 设为 `32001`。
7. 将 Multicast IP 设为 `239.192.255.251`。
8. 点击 `Start`。

预期结果：

- 服务状态在树中变为 `Running`。
- 运行时字段在运行期间被锁定。
- 运行日志包含 `Offered service` 和 `Started service`。
- 问题面板无此启动的验证错误。

结果：

- 通过 / 失败：
- 备注：

清理：

- 点击 `Stop`。
- 确认服务状态恢复为 `Stopped`。

## 7. Server 角色事件发布

### GUI-20 UDP 周期事件单次发布

服务测试夹具：

- 文件：`ADC40_SOC\0x080E.json`
- 服务：`0x080E`
- 事件：`VehicleInfo`
- 传输：UDP
- 发送策略：Cycle

步骤：

1. 选择服务 `0x080E`。
2. 将 Role 设为 `Server`。
3. 配置：
   - Local IP：`127.0.0.1`
   - Remote IP：`127.0.0.1`
   - Server Port：`32000`
   - Client Port：`32001`
   - Multicast IP：`239.192.255.251`
4. 点击 `Start`。
5. 选择事件 `VehicleInfo`。
6. 设置载荷 JSON：

```json
{
  "VehicleInfo": {
    "VehicleSpeed": 12.5,
    "Odometer": 99.25
  }
}
```

7. 点击 `Publish Once`。

预期结果：

- 运行日志包含 `Published event VehicleInfo`。
- 消息追踪包含一个 TX 行：
  - `element_type` = `Event`
  - `element_name` = `VehicleInfo`
  - `transport` = `UDP`
  - `raw_payload_hex` 非空。
  - `result` = `success`

可选抓包：

- Wireshark 应显示涉及配置端口及服务/事件 ID 的 SOME/IP 或 UDP 流量。

结果：

- 通过 / 失败：
- 备注：

### GUI-21 UDP 周期事件启动/停止

从 GUI-20 继续。

步骤：

1. 选择事件 `VehicleInfo`。
2. 保持相同载荷 JSON。
3. 点击 `Start Cycle`。
4. 等待至少 3 秒。
5. 点击 `Stop Cycle`。

预期结果：

- 运行日志包含 `Started cycle event VehicleInfo`。
- 消息追踪收到多条 `VehicleInfo` 的 TX 行。
- 运行日志包含 `Stopped cycle event VehicleInfo`。
- 停止周期后，不再新增 `VehicleInfo` TX 行。

结果：

- 通过 / 失败：
- 备注：

清理：

- 停止服务。

### GUI-22 TCP 触发事件单次发布

服务测试夹具：

- 文件：`ADC40_SOC\0x080A.json`
- 服务：`0x080A`
- 事件：`IntellgntSwtDecoupSts`
- 传输：TCP
- 发送策略：Trigger

步骤：

1. 选择服务 `0x080A`。
2. 将 Role 设为 `Server`。
3. 配置有效的本地/远端 IP 和端口。
4. 点击 `Start`。
5. 选择事件 `IntellgntSwtDecoupSts`。
6. 设置载荷 JSON：

```json
{
  "IntellgntSwtDecoupSts": [1, 2, 3]
}
```

7. 点击 `Publish Once`。

预期结果：

- 运行日志包含 `Published event IntellgntSwtDecoupSts`。
- 消息追踪包含 TX 事件行，`transport` = `TCP`。
- `Start Cycle` 对该触发事件禁用。

结果：

- 通过 / 失败：
- 备注：

清理：

- 停止服务。

## 8. Client 角色订阅与接收

这些测试需要以下条件之一：

- 一台提供匹配服务并发布事件的对端设备/服务器，或
- 一个可以通过真实后端提供/发布同一服务的受控本地环境。

### GUI-30 Client 订阅 UDP 事件

服务测试夹具：

- 服务：`0x080E`
- 事件：`VehicleInfo`
- 传输：UDP

步骤：

1. 确保对端服务器正在提供服务 `0x080E` 并可发布 `VehicleInfo`。
2. 在 GUI 中选择服务 `0x080E`。
3. 将 Role 设为 `Client`。
4. 配置：
   - Local IP：本地测试机器 IP
   - Remote IP：对端服务器 IP
   - Server Port：对端服务器 SOME/IP 端口
   - Client Port：本地客户端端口
   - Multicast IP：配置的 SD 组播 IP
5. 点击 `Start`。
6. 选择事件 `VehicleInfo`。
7. 点击 `Subscribe`。
8. 触发对端服务器发布 `VehicleInfo`。

预期结果：

- 运行日志包含 `Found service`（启动成功时）。
- 运行日志包含 `Subscribed eventgroup`。
- 消息追踪包含 RX 事件行：
  - `element_type` = `Event`
  - `element_name` = `VehicleInfo`
  - `transport` = `UDP`
  - `payload_decode_status` = `ok`
  - `decoded_payload` 包含 `VehicleInfo`。

结果：

- 通过 / 失败：
- 备注：

### GUI-31 Client 取消订阅事件

从 GUI-30 继续。

步骤：

1. 点击 `Unsubscribe`。
2. 再次触发对端服务器发布同一事件。

预期结果：

- 运行日志包含 `Unsubscribed eventgroup`。
- 取消订阅后无新的 RX 追踪行出现。

结果：

- 通过 / 失败：
- 备注：

## 9. Field Getter 与 Notifier

### GUI-40 Client Field Getter

服务测试夹具：

- 文件：`ADC40_SOC\0x080C.json`
- 服务：`0x080C`
- 字段：`VertHeiRmdSts`
- Getter ID：`0x1001`
- Notifier ID：`0x9001`
- 传输：TCP

步骤：

1. 确保对端服务器提供服务 `0x080C` 并响应 getter `0x1001`。
2. 在 GUI 中选择服务 `0x080C`。
3. 将 Role 设为 `Client`。
4. 配置对端的运行时 IP 和端口。
5. 点击 `Start`。
6. 选择字段 `VertHeiRmdSts`。
7. 设置载荷 JSON：

```json
{
  "VertHeiRmdSts": 1
}
```

8. 点击 `Get`。

预期结果：

- 运行日志包含 `Field getter VertHeiRmdSts result=success`。
- 消息追踪包含：
  - TX `FieldGetter`
  - RX `FieldGetter`
  - `payload_decode_status` = `ok`
  - 解码的载荷包含 `VertHeiRmdSts`。

结果：

- 通过 / 失败：
- 备注：

### GUI-41 Server Field Notifier

步骤：

1. 选择服务 `0x080C`。
2. 将 Role 设为 `Server`。
3. 配置运行时 IP 和端口。
4. 点击 `Start`。
5. 选择字段 `VertHeiRmdSts`。
6. 设置载荷 JSON：

```json
{
  "VertHeiRmdSts": 1
}
```

7. 点击 `Notify`。

预期结果：

- 运行日志包含 `Field notifier VertHeiRmdSts`。
- 消息追踪包含 TX 行：
  - `element_type` = `FieldNotifier`
  - `element_name` = `VertHeiRmdSts`
  - `transport` = `TCP`
  - `result` = `success`

可选对端验证：

- 已订阅 eventgroup `0x0001` 的对端客户端收到 notifier `0x9001`。

结果：

- 通过 / 失败：
- 备注：

## 10. Method 能力门控

### GUI-50 FF Method 显示受限状态

服务测试夹具：

- 服务：`0x080D`
- 方法：`SecondStartCtrl`
- RR/FF：`FF`
- 传输：UDP

步骤：

1. 选择服务 `0x080D`。
2. 将 Role 设为 `Client`。
3. 配置运行时 IP 和端口。
4. 点击 `Start`。
5. 选择方法 `SecondStartCtrl`。
6. 确认操作状态文本提到 fire-and-forget 方法执行受限。
7. 设置载荷 JSON：

```json
{
  "SecondStartCtrlCmd": 1
}
```

8. 点击 `Call`。

预期结果：

- 操作面板明确说明 FF 方法受限。
- 运行日志包含 `Called method SecondStartCtrl result=limited`。
- 消息追踪包含 TX Method 行，`result` = `limited`。
- 这不被视为端到端 FF 方法证明。

结果：

- 通过 / 失败：
- 备注：

### GUI-51 Field Setter 保持不可用/门控

步骤：

1. 选择服务 `0x080C` 下的字段 `VertHeiRmdSts`。
2. 检查操作状态文本。

预期结果：

- 状态文本包含 `setter unavailable` 或门控措辞。
- MVP-1 不声称任何成功的 Field Setter 路径。

结果：

- 通过 / 失败：
- 备注：

## 11. 导出证据

### GUI-60 导出追踪和日志

步骤：

1. 完成至少一次服务器事件发布和一次字段操作。
2. 使用 File 菜单导出：
   - Message Trace CSV
   - Message Trace JSON
   - Run Log TXT
   - Run Log JSON
3. 将输出保存到测试证据文件夹。

预期结果：

- CSV 以 `timestamp,direction` 开头。
- JSON 导出为有效 JSON。
- 运行日志包含服务启动/停止和操作消息。
- 追踪包含服务 ID、元素 ID、传输层、原始载荷十六进制、解码载荷和结果。

证据文件夹：

```text
<在此填写路径>
```

结果：

- 通过 / 失败：
- 备注：

## 12. 最终验收检查清单

逐项标记：

- [ ] GUI 使用真实 `someipy` 后端启动。
- [ ] `ADC40_SOC` 定义成功导入。
- [ ] 服务树显示角色和运行/停止状态。
- [ ] 运行时验证捕获缺失/无效端口。
- [ ] 运行时验证在适用情况下捕获本地 IP/端口占用问题。
- [ ] Server 角色可以启动并提供服务。
- [ ] Client 角色可以启动并找到可用服务。
- [ ] UDP 事件单次发布记录 TX 追踪。
- [ ] UDP 周期事件启动/停止记录重复 TX 追踪并干净停止。
- [ ] TCP 触发事件单次发布记录 TX 追踪。
- [ ] Client 事件订阅记录订阅和带对端/服务器输入的 RX 追踪。
- [ ] Client 事件取消订阅停止该事件的新 RX 追踪。
- [ ] Field getter 记录 TX 和 RX 追踪及解码载荷。
- [ ] Field notifier 记录 TX 追踪，且在可用时能被对端客户端观测到。
- [ ] FF method 操作被明确标记为受限。
- [ ] RR method 和 field setter 不被声称支持。
- [ ] 运行日志和消息追踪导出产物可读。
- [ ] `python scripts\run_protocol_spike.py --mode real --start-daemon` 通过支持的场景。
- [ ] 打包应用冒烟测试成功退出。

## 13. 缺陷记录模板

每个缺陷使用一条记录：

```text
ID：
测试用例：
服务：
角色：
传输层：
本地 IP/端口：
远端 IP/端口：
载荷：
预期：
实际：
运行日志摘录：
消息追踪摘录：
Wireshark 证据：
复现步骤：
严重程度：
负责人：
状态：
```

## 14. 签收

| 角色 | 姓名 | 结果 | 日期 | 备注 |
| --- | --- | --- | --- | --- |
| 测试人员 | | 通过 / 失败 | | |
| 开发人员 | | 通过 / 失败 | | |
| 评审人员 | | 通过 / 失败 | | |
