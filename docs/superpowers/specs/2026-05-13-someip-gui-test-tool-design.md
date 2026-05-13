# SOME/IP GUI Test Tool Design

Date: 2026-05-13

## 1. Product Positioning

This project is a Windows x64 desktop SOME/IP manual test tool for test engineers. The first release focuses on GUI-based manual testing against peer devices. CLI automation is planned for a later phase, but the architecture and project file format must be reusable by a future CLI.

The tool uses PySide for the desktop application. The first protocol implementation should use `someipy`, but all protocol calls must go through a replaceable adapter interface so the backend can later switch to `vsomeip_py` or an internal SOME/IP stack if needed.

## 2. Phase Goals

MVP-1 focuses on protocol loop closure:

- Import `ADC40_SOC/*.json` service definition files.
- Select Client or Server role per service.
- Support TCP and UDP according to each service, method, event, or field definition.
- Keep JSON files as base definitions and save runtime changes as project overrides.
- Support method call, event subscription/publish, and field getter/setter/notifier behavior.
- Support structured payload editing and raw hex editing.
- Provide run logs, message trace, and JSON/CSV trace export.
- Package as a Windows x64 desktop application.

MVP-2 focuses on GUI efficiency:

- Service tree, search, filtering, payload forms, project management, and trace usability.
- Save and load project files.
- Save and execute simple action sequences from the GUI.

MVP-3 focuses on stability and engineering quality:

- Multi-service concurrency.
- Long-running cycle events.
- TCP failure handling and reconnect visibility.
- Resource cleanup on stop and exit.
- Network, port, and payload validation.

## 3. Architecture

Use a three-layer architecture:

1. PySide GUI layer
2. Core Service layer
3. Protocol Adapter layer

The GUI must not call `someipy` directly. It should call Core services, and Core should call the protocol adapter through a stable interface.

### 3.1 PySide GUI Layer

The GUI is responsible for:

- Browsing imported service definitions.
- Selecting Client or Server role per service.
- Editing runtime configuration such as IP, port, transport override, SD timing, TTL, cycle time, and payload defaults.
- Showing structured payload forms and raw hex payload input.
- Starting and stopping services.
- Offering and finding services.
- Calling methods.
- Subscribing to and publishing events.
- Getting, setting, and notifying fields.
- Showing run logs, message trace, and problems.
- Saving and loading project files.
- Restoring recent sessions.

### 3.2 Core Service Layer

The Core layer is shared by the GUI and future CLI. It is responsible for:

- Loading and validating service definition JSON files.
- Mapping JSON to internal domain models:
  - `ServiceDefinition`
  - `MethodDefinition`
  - `EventDefinition`
  - `FieldDefinition`
  - `DatatypeDefinition`
  - `DeploymentConfig`
- Merging base definitions with runtime overrides.
- Managing active services and test sessions.
- Managing subscriptions, cycle event tasks, method call history, and trace records.
- Managing project files and simple action sequences.
- Providing unified error handling and log events.

### 3.3 Protocol Adapter Layer

Define a `SomeIpAdapter` interface with operations such as:

- `start_service`
- `stop_service`
- `offer_service`
- `find_service`
- `call_method`
- `register_method_handler`
- `subscribe_eventgroup`
- `unsubscribe_eventgroup`
- `publish_event`
- `register_event_handler`
- `shutdown`

The first implementation is `SomeipyAdapter`. Future implementations may include `VsomeipAdapter`, `InternalSomeIpAdapter`, or `MockAdapter`.

The adapter reports:

- Protocol status.
- Errors and timeouts.
- Received messages.
- Raw payload bytes.
- Metadata available from the backend, such as session id, message type, and return code.

### 3.4 Payload Codec Layer

Payload encoding and decoding must be independent from both GUI and protocol adapter.

The codec is responsible for:

- Generating structured form models from JSON datatype definitions.
- Encoding structured values to payload bytes.
- Decoding payload bytes to structured values.
- Supporting raw hex passthrough.

The first release covers datatypes already present in the current JSON files:

- `BasicType`
- `Typedef`
- `Enum`
- `Integer`
- `Float`
- `String`
- `Array`
- `Struct`

Initial encoding follows project conventions for these types. The codec must be isolated so future changes to endian, alignment, dynamic length, or string encoding rules do not affect GUI or adapter code.

## 4. JSON Service Definition Mapping

The tool imports JSON files under `ADC40_SOC`. JSON files are treated as base definitions. The tool does not modify them directly.

### 4.1 Service Mapping

Each JSON file maps to a `ServiceDefinition`.

Key fields:

- `ServiceInterfaceID` -> service id
- `ServiceInterfaceName` -> service name
- `Deployment.Service Interface Instance ID` -> instance id
- `Deployment.Major Version` -> major version
- `Deployment.Minor Version` -> minor version
- `Deployment.Server ECU`
- `Deployment.Client ECU`
- `Deployment.Server IP Address`
- `Deployment.Client IP Address`
- `Deployment.Multicast IP Address`
- `Deployment.Transport Protocol`
- `Deployment.VLAN ID`
- `Deployment.VLAN Priority`
- SD timing and TTL fields

The current JSON files use `/` for `Server Port` and `Client Port`. The GUI must require runtime port input or a project override before starting a service.

Role-based defaults:

- If the tool simulates Server, local ECU/IP defaults to JSON Server ECU/IP.
- If the tool simulates Client, local ECU/IP defaults to JSON Client ECU/IP.
- The opposite side becomes the default remote endpoint.
- All inferred values may be overridden at runtime.

### 4.2 Method Mapping

Elements with `TransmissionType = "Method"` map to `MethodDefinition`.

Fields:

- `ElementName` -> method name
- `ElementID` -> method id
- `RR/FF` -> call mode
- `L4-Protocol` -> TCP or UDP
- `Parameters` -> request/response payload definition

Behavior:

- `FF` means fire-and-forget. The client sends the request and does not wait for a response.
- `RR` means request-response. The client waits for a response, timeout, or error.
- Client role can call methods.
- Server role can register handlers.
- For `RR`, Server role must allow response payload configuration.

### 4.3 Event Mapping

Elements with `TransmissionType = "Event"` map to `EventDefinition`.

Fields:

- `ElementName` -> event name
- `ElementID` -> event id
- `EventgroupName`
- `EventgroupID`
- `L4-Protocol` -> TCP or UDP
- `SendStrategy`
- `CycleTime`
- `Parameters` -> event payload definition

Behavior:

- Client role can find service, subscribe eventgroup, unsubscribe, and receive events.
- Server role can offer service, offer event/eventgroup, publish events, and cycle publish events.
- `SendStrategy = "Trigger"` supports manual publish.
- `SendStrategy = "Cycle"` supports periodic publish using `CycleTime`, with runtime override.
- Multiple eventgroups/events may be subscribed at the same time.
- Events in the same service may use different transport protocols according to `L4-Protocol`.

### 4.4 Field Mapping

Elements with `TransmissionType = "Field"` map to field parts and are then grouped by `ElementName`.

Example from `0x080C.json`:

- `VertHeiRmdSts`, `FieldType = "Getter"`, `ElementID = 0x1001`
- `VertHeiRmdSts`, `FieldType = "Notifier"`, `ElementID = 0x9001`

These become one `FieldDefinition`:

- field name: `VertHeiRmdSts`
- getter id: `0x1001`
- setter id: absent unless present in JSON
- notifier id: `0x9001`
- eventgroup id: `0x0001`
- transport: TCP
- datatype: `VertHeiRmd_Enum`

GUI behavior:

- Default Field view groups Getter, Setter, and Notifier together.
- Raw Element debug view shows each original ElementID, EventgroupID, transport, and payload definition.
- Client role can call Getter, call Setter if present, and subscribe Notifier.
- Server role can respond to Getter, handle Setter if present, and publish Notifier.

## 5. GUI Interaction Design

The main window has four primary areas:

1. Service tree
2. Runtime configuration panel
3. Operation panel
4. Log, trace, and problems panel

### 5.1 Service Tree

The service tree shows:

- ECU groups
- Service nodes
- Method nodes
- Event nodes
- Field nodes
- Eventgroup nodes

Each service node shows:

- Service name
- Service id
- Instance id
- Role: Client, Server, or disabled
- State: Stopped, Starting, Running, or Error

Filtering:

- Service name or id
- Element name or id
- Method/Event/Field
- TCP/UDP
- Client/Server role

### 5.2 Runtime Configuration Panel

For the selected service, show:

- Role: Client or Server
- Local ECU and local IP
- Remote ECU and remote IP
- Server port and client port
- Multicast IP
- Default transport
- VLAN ID and VLAN Priority
- SD timing and TTL advanced settings

Before service start, validate:

- Local IP belongs to a local network adapter.
- Required ports are configured.
- Ports are not occupied.
- Multicast configuration is present.
- Transport configuration is valid.
- Firewall and permission warnings are visible.

The first release does not need to automatically configure VLAN or firewall rules.

### 5.3 Operation Panel

The operation panel changes by selected node type.

For Method:

- Show method id, RR/FF, transport, and description.
- Show structured payload form and raw hex mode.
- Client role has a Call action.
- Server role can configure method handler and response payload.

For Event:

- Show event id, eventgroup id, send strategy, cycle time, transport, and description.
- Client role has Subscribe and Unsubscribe actions.
- Server role has Publish Once, Start Cycle, and Stop Cycle actions.
- Received and sent event payloads are shown as both decoded values and raw hex.

For Field:

- Show grouped Getter, Setter, and Notifier areas.
- Getter supports Client get and Server response configuration.
- Setter supports Client set and Server handling when present.
- Notifier supports Client subscribe and Server publish.
- Raw Element debug view is available.

### 5.4 Logs, Trace, and Problems

The bottom panel has tabs:

- Run Log
- Message Trace
- Problems

Run Log shows user operations and system state changes.

Message Trace shows SOME/IP messages sent and received by the tool.

Problems shows current configuration and runtime issues that need attention.

## 6. Project File, Session, and CLI Preparation

The application supports both project files and recent session recovery.

### 6.1 Project File

The project file stores runtime configuration and action sequences. It references service definition files but does not copy or modify them.

It should include:

- Schema version
- Project name
- Definition root path
- Imported service file list
- Enabled services
- Role per service
- Runtime overrides:
  - local IP
  - remote IP
  - server port
  - client port
  - multicast IP
  - transport override
  - SD timing override
  - TTL override
- Payload defaults:
  - method request
  - method response
  - event publish payload
  - field getter response
  - field setter request
  - field notifier payload
- Event subscriptions
- Cycle event settings
- Simple action sequences

Use JSON for the first project file format.

Example shape:

```json
{
  "schema_version": "1.0",
  "project_name": "ADC40_SOC manual test",
  "definition_root": "ADC40_SOC",
  "services": [],
  "sequences": []
}
```

### 6.2 Simple Action Sequences

The first release supports simple sequential actions, not a full test assertion framework.

Initial action types:

- `start_service`
- `stop_service`
- `find_service`
- `offer_service`
- `subscribe_eventgroup`
- `unsubscribe_eventgroup`
- `call_method`
- `publish_event`
- `start_cycle_event`
- `stop_cycle_event`
- `field_get`
- `field_set`
- `field_notify`
- `wait`
- `export_trace`

Action sequences can be run from the GUI. Later, the CLI can execute the same sequences.

### 6.3 CLI Preparation

A future CLI should reuse:

- JSON service parsing
- Project file parsing
- Runtime config merge
- Payload codec
- Protocol adapter
- Trace/export logic

Possible future commands:

```powershell
someip-tool run project.json
someip-tool run project.json --sequence smoke
someip-tool list-services project.json
someip-tool export-trace project.json --format csv
```

The CLI does not reuse PySide GUI components.

### 6.4 Recent Session

Recent session data is local to the user's machine and is not intended for team sharing.

It may include:

- Recent project files
- Recent JSON definition directory
- Window layout
- Last selected network adapter/IP
- Recent payload values
- Recent trace export directory

## 7. Logging, Trace, and Error Handling

### 7.1 Run Log

Run Log records high-level operations and state changes.

Each entry includes:

- timestamp
- level: debug, info, warning, or error
- source: GUI, Core, Adapter, Codec, or Project
- message
- related service id if applicable
- related element id if applicable
- error detail if applicable

### 7.2 Message Trace

Message Trace records messages sent and received by the tool.

Each trace entry should include:

- timestamp
- direction: TX or RX
- role: Client or Server
- service name
- service id
- instance id
- major/minor version
- element type: Method, Event, FieldGetter, FieldSetter, or FieldNotifier
- element name
- element id
- eventgroup id if applicable
- transport: TCP or UDP
- local endpoint
- remote endpoint
- session id if available
- message type if available
- return code if available
- RR/FF if applicable
- raw payload hex
- decoded payload JSON
- payload decode status
- duration in milliseconds for RR method calls
- result: success, timeout, error, or cancelled
- error message if applicable

Trace UI supports filtering by:

- service
- Method/Event/Field
- TX/RX
- TCP/UDP
- error state

### 7.3 Export

First release supports:

- Run Log as `.txt`
- Run Log as `.json`
- Message Trace as `.csv`
- Message Trace as `.json`

HTML report export is a later enhancement.

### 7.4 Error Handling

Configuration errors:

- Missing JSON fields
- Port not configured
- IP not found on local network adapters
- Invalid transport
- Unsupported datatype
- Payload value outside min/max

Runtime errors:

- Service start failure
- `someipyd` start failure
- Port occupied
- Multicast join failure
- TCP connection failure
- Find service timeout
- Subscribe failure
- RR method timeout

Protocol or data errors:

- Payload encode failure
- Payload decode failure
- Unknown service or element id
- Payload length mismatch
- Non-OK return code
- Eventgroup mismatch

Display rules:

- Critical errors may show a dialog.
- All errors go to Run Log.
- Active configuration issues go to Problems.
- Message-related errors go to Message Trace.
- Recoverable errors should provide retry actions where practical.

## 8. someipy Spike

Before building the full GUI, run a small technical spike to validate `someipy` on Windows x64.

The spike must verify:

1. `someipy` can be installed and run on Windows x64.
2. `someipyd` can be started and stopped by the application.
3. UDP FF method works with `0x080D.json` `SecondStartCtrl`.
4. TCP method works with `0x0F01.json` such as `AudioRecPopupReq`.
5. UDP event works with `0x080E.json` `VehicleInfo`, including cycle publish and struct payload decode.
6. TCP event works with `0x080A.json` or `0x0F01.json`.
7. Field Getter/Notifier works with `0x080C.json` `VertHeiRmdSts`.
8. At least two services can run at the same time, one TCP and one UDP.
9. Current JSON datatypes can be encoded and decoded at a basic level.
10. PyInstaller or Nuitka can package a minimal scenario.

If a critical spike item fails, evaluate `vsomeip_py` or an internal SOME/IP stack while keeping the GUI, Core, project file, and codec design stable.

## 9. MVP Acceptance Criteria

### MVP-1: Protocol Loop Closure

- Windows x64 PySide application starts.
- `ADC40_SOC/*.json` files import successfully.
- Service, method, event, field, datatype, and deployment data are parsed.
- Each service can be configured as Client or Server.
- Role-based IP inference works and can be overridden.
- Ports can be configured or overridden.
- Services can start and stop.
- UDP FF method call works.
- TCP method call works.
- UDP event subscription and cycle receive works.
- TCP event subscription and trigger publish works.
- Field Getter and Notifier basic operations work.
- At least two services can run concurrently.
- Message Trace records TX/RX, service id, element id, transport, raw hex, and decoded payload.
- Trace can export JSON and CSV.
- Packaged Windows x64 app can run at least one method and one event scenario.

### MVP-2: GUI Efficiency

- Service tree shows service, method, event, and field hierarchy.
- Search and filters work.
- Structured payload forms support enum, integer, float, string, array, and struct.
- Raw hex mode is available.
- Event manual publish and cycle publish work from the GUI.
- Field grouped view and raw Element debug view are available.
- Run Log, Message Trace, and Problems panels are usable.
- Project files can be saved and loaded.
- Recent session can be restored.
- Simple action sequences can be saved and run in order.

### MVP-3: Stability and Engineering

- Multiple services can run without blocking each other.
- Multiple eventgroups can be subscribed at the same time.
- Cycle events can run for extended periods.
- RR method timeout is handled.
- TCP failure and disconnects are visible to the user.
- Stopping services cleans up resources.
- Application exit cleans up `someipyd`, cycle tasks, sockets, and adapter resources.
- Port occupancy is detected.
- Network adapter/IP mismatch is detected.
- Payload codec failures are visible.
- Trace memory usage is controlled for large runs.
- Packaged app runs on target Windows test machines without a source environment.
- Known limitations are documented, including VLAN and firewall handling.

## 10. Known First-Release Limits

- VLAN and firewall are detected or shown as warnings, not automatically configured.
- HTML report export is not required for MVP.
- Full CLI automation is not part of the first GUI release.
- Full AUTOSAR ARXML import is not part of the first release.
- Complex conditional assertions in action sequences are not part of the first release.
- `someipy` is treated as the first backend, not a permanent hard dependency.
