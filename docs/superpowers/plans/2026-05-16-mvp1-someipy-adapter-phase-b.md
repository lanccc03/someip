# MVP-1 Someipy Adapter Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the proven someipy loopback spike paths into the formal `SomeipyAdapter` so Core runtime operations can use real event and field SOME/IP behavior through the adapter boundary.

**Architecture:** Keep GUI and Core isolated from `someipy`; all protocol work stays inside `src/someip_gui_tool/adapters/someipy_adapter.py` and reuses `SomeipyServiceFactory`. The adapter owns per-service someipy server/client instances, dispatches received events into existing `AdapterEvent` callbacks, and keeps current fire-and-forget method limitations explicit instead of reporting false success.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, someipy, existing `SomeipydProcess`, existing `SomeipyServiceFactory`, existing `SomeIpAdapter` contract.

---

## Scope

Phase B implements the formal adapter runtime slice that Phase A intentionally left as a skeleton:

- Create and cache per-service someipy server/client instances.
- Start and stop service offers through `ServerServiceInstance.start_offer()` and `stop_offer()`.
- Find services through `ClientServiceInstance.is_available()`.
- Subscribe and unsubscribe eventgroups through `ClientServiceInstance`.
- Publish events through `ServerServiceInstance.send_event()`.
- Dispatch received event and field notifier payloads through registered `AdapterEvent` handlers.
- Execute field getter calls through `ClientServiceInstance.call_method()`.
- Publish field notifier events through `ServerServiceInstance.send_event()`.
- Optionally start and stop an owned `someipyd` process for app-managed adapter usage.
- Preserve `FF` method reporting as `limited`; do not claim current ADC40 method support.

This plan does not wire GUI buttons to `RuntimeSession`, does not add project save/load, does not add payload forms, and does not solve peer-device runtime configuration. Those belong after the formal adapter path is usable and tested.

## Current Baseline

- `docs/superpowers/plans/2026-05-15-mvp1-runtime-gui-ops.md` implemented Phase A.
- `src/someip_gui_tool/adapters/someipy_adapter.py` currently connects to someipyd but returns skeleton behavior for most protocol operations.
- `scripts/run_protocol_spike.py --mode real --start-daemon` proves these paths outside the formal adapter:
  - someipy API available.
  - someipyd starts.
  - UDP event subscribe/send/callback works.
  - TCP event subscribe/send/callback works.
  - `0x080C` field getter and notifier work.
  - Current FF methods remain skipped.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest` passed with 129 tests before Phase B.

## File Structure

- Create: `tests/fakes_someipy_runtime.py` - reusable fake someipy API, server, client, eventgroup, service builder, and daemon objects for deterministic adapter tests.
- Modify: `tests/test_someipy_adapter.py` - replace Phase A skeleton assertions with real lifecycle, event, field, and daemon ownership behavior.
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py` - implement per-service runtime state and real someipy operations.
- Modify: `src/someip_gui_tool/adapters/capabilities.py` only if final behavior changes documented backend capabilities.
- Do not modify GUI files in this plan.

---

### Task 1: Add a Reusable Fake someipy Runtime Harness

**Files:**
- Create: `tests/fakes_someipy_runtime.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Create the fake someipy runtime helper**

Create `tests/fakes_someipy_runtime.py` with:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable


@dataclass(frozen=True)
class FakeMethod:
    id: int
    protocol: str
    method_handler: Callable[[bytes, tuple[str, int]], object] | None = None


@dataclass(frozen=True)
class FakeEvent:
    id: int
    protocol: str


@dataclass(frozen=True)
class FakeEventGroup:
    id: int
    events: list[FakeEvent]

    @property
    def has_udp(self) -> bool:
        return any(event.protocol == "UDP" for event in self.events)

    @property
    def has_tcp(self) -> bool:
        return any(event.protocol == "TCP" for event in self.events)

    def to_json(self) -> str:
        return f"eventgroup:{self.id}"


class FakeService:
    def __init__(
        self,
        *,
        id: int,
        major_version: int,
        minor_version: int,
        methods: list[FakeMethod],
        eventgroups: list[FakeEventGroup],
    ) -> None:
        self.id = id
        self.major_version = major_version
        self.minor_version = minor_version
        self.methods = {method.id: method for method in methods}
        self.eventgroups = {group.id: group for group in eventgroups}
        self.eventgroupids = set(self.eventgroups)


class FakeServiceBuilder:
    def __init__(self) -> None:
        self.service_id: int | None = None
        self.major_version: int | None = None
        self.minor_version: int | None = None
        self.methods: list[FakeMethod] = []
        self.eventgroups: list[FakeEventGroup] = []

    def with_service_id(self, id: int) -> FakeServiceBuilder:
        self.service_id = id
        return self

    def with_major_version(self, major_version: int) -> FakeServiceBuilder:
        self.major_version = major_version
        return self

    def with_minor_version(self, minor_version: int) -> FakeServiceBuilder:
        self.minor_version = minor_version
        return self

    def with_method(self, method: FakeMethod) -> FakeServiceBuilder:
        self.methods.append(method)
        return self

    def with_eventgroup(self, eventgroup: FakeEventGroup) -> FakeServiceBuilder:
        self.eventgroups.append(eventgroup)
        return self

    def build(self) -> FakeService:
        if self.service_id is None:
            raise ValueError("service id was not configured")
        if self.major_version is None:
            raise ValueError("major version was not configured")
        if self.minor_version is None:
            raise ValueError("minor version was not configured")
        return FakeService(
            id=self.service_id,
            major_version=self.major_version,
            minor_version=self.minor_version,
            methods=self.methods,
            eventgroups=self.eventgroups,
        )


class FakeDaemon:
    def __init__(self, api: FakeSomeipyApi) -> None:
        self.api = api
        self.disconnected = False

    async def disconnect_from_daemon(self) -> None:
        self.disconnected = True


class FakeServerServiceInstance:
    def __init__(
        self,
        *,
        daemon: FakeDaemon,
        service: FakeService,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        ttl: int = 0,
        cyclic_offer_delay_ms: int = 2000,
    ) -> None:
        self.daemon = daemon
        self.service = service
        self.instance_id = instance_id
        self.endpoint_ip = endpoint_ip
        self.endpoint_port = endpoint_port
        self.ttl = ttl
        self.cyclic_offer_delay_ms = cyclic_offer_delay_ms
        self.start_awaited = False
        self.stop_awaited = False
        self.sent_events: list[tuple[int, int, bytes]] = []
        daemon.api.servers.append(self)

    async def start_offer(self) -> None:
        self.start_awaited = True

    async def stop_offer(self) -> None:
        self.stop_awaited = True

    def send_event(self, eventgroup_id: int, event_id: int, payload: bytes) -> None:
        self.sent_events.append((eventgroup_id, event_id, payload))
        for client in self.daemon.api.clients:
            if client.service.id == self.service.id:
                client.deliver_event(eventgroup_id, event_id, payload)


class FakeClientServiceInstance:
    def __init__(
        self,
        *,
        daemon: FakeDaemon,
        service: FakeService,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        client_id: int = 0,
    ) -> None:
        self.daemon = daemon
        self.service = service
        self.instance_id = instance_id
        self.endpoint_ip = endpoint_ip
        self.endpoint_port = endpoint_port
        self.client_id = client_id
        self.callback: Callable[[int, bytes], None] | None = None
        self.subscribed_eventgroups: list[tuple[int, int]] = []
        self.unsubscribed_eventgroups: list[int] = []
        daemon.api.clients.append(self)

    def register_callback(self, callback: Callable[[int, bytes], None]) -> None:
        self.callback = callback

    async def is_available(self) -> bool:
        sequence = self.daemon.api.availability_sequences.get(self.service.id, [True])
        index = self.daemon.api.availability_calls.get(self.service.id, 0)
        self.daemon.api.availability_calls[self.service.id] = index + 1
        if index < len(sequence):
            return sequence[index]
        return sequence[-1]

    def subscribe_eventgroup(
        self,
        eventgroup: FakeEventGroup,
        ttl_subscription_seconds: int,
    ) -> None:
        self.subscribed_eventgroups.append((eventgroup.id, ttl_subscription_seconds))

    def unsubscribe_eventgroup(self, eventgroup: FakeEventGroup) -> None:
        self.unsubscribed_eventgroups.append(eventgroup.id)

    async def call_method(self, method_id: int, payload: bytes) -> object:
        server = self.daemon.api.server_for_service(self.service.id)
        method = server.service.methods[method_id]
        if method.method_handler is None:
            return self.daemon.api.method_result(payload=b"")
        result = method.method_handler(payload, (self.endpoint_ip, self.endpoint_port))
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def deliver_event(self, eventgroup_id: int, event_id: int, payload: bytes) -> None:
        subscribed_ids = {group_id for group_id, ttl in self.subscribed_eventgroups}
        if eventgroup_id in subscribed_ids and self.callback is not None:
            self.callback(event_id, payload)


class FakeSomeipyApi:
    class TransportLayerProtocol:
        TCP = "TCP"
        UDP = "UDP"

    class MessageType:
        RESPONSE = "RESPONSE"
        ERROR = "ERROR"

    class ReturnCode:
        E_OK = "E_OK"
        E_NOT_OK = "E_NOT_OK"

    ServiceBuilder = FakeServiceBuilder
    Method = FakeMethod
    Event = FakeEvent
    EventGroup = FakeEventGroup

    def __init__(
        self,
        *,
        availability_sequences: dict[int, list[bool]] | None = None,
        connect_sleep: float | None = None,
    ) -> None:
        self.connect_sleep = connect_sleep
        self.connect_started_count = 0
        self.connect_configs: list[dict[str, object]] = []
        self.availability_sequences = availability_sequences or {}
        self.availability_calls: dict[int, int] = {}
        self.servers: list[FakeServerServiceInstance] = []
        self.clients: list[FakeClientServiceInstance] = []
        self.daemon = FakeDaemon(self)

    async def connect_to_someipy_daemon(self, config: dict[str, object]) -> FakeDaemon:
        self.connect_started_count += 1
        if self.connect_sleep is not None:
            await asyncio.sleep(self.connect_sleep)
        self.connect_configs.append(config)
        return self.daemon

    def ServerServiceInstance(self, **kwargs: object) -> FakeServerServiceInstance:
        return FakeServerServiceInstance(**kwargs)

    def ClientServiceInstance(self, **kwargs: object) -> FakeClientServiceInstance:
        return FakeClientServiceInstance(**kwargs)

    def MethodResult(self) -> object:
        return self.method_result(payload=b"")

    def method_result(self, payload: bytes) -> object:
        return SimpleNamespace(
            message_type=self.MessageType.RESPONSE,
            return_code=self.ReturnCode.E_OK,
            payload=payload,
        )

    def server_for_service(self, service_id: int) -> FakeServerServiceInstance:
        for server in self.servers:
            if server.service.id == service_id:
                return server
        raise KeyError(f"server for service 0x{service_id:04X} was not started")
```

- [ ] **Step 2: Replace local fake API classes in `tests/test_someipy_adapter.py`**

At the top of `tests/test_someipy_adapter.py`, remove the existing `FakeDaemon`, `FakeApi`, `SyncDisconnectDaemon`, and `SyncDisconnectApi` classes. Add:

```python
from tests.fakes_someipy_runtime import FakeSomeipyApi
```

Update existing adapter construction sites from `FakeApi()` and `SyncDisconnectApi()` to `FakeSomeipyApi()`.

- [ ] **Step 3: Run existing adapter tests after the fake helper refactor**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py -q
```

Expected: PASS. This task only extracts and standardizes the fake runtime helper; it does not change adapter behavior.

- [ ] **Step 4: Commit the fake runtime harness refactor**

Run:

```bash
git add tests/fakes_someipy_runtime.py tests/test_someipy_adapter.py
git commit -m "test: add fake someipy runtime harness"
```

Expected: commit succeeds with all existing adapter tests passing.

---

### Task 2: Implement Per-Service someipy Runtime Lifecycle

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Add lifecycle tests for creation, reuse, and stop**

Add these tests to `tests/test_someipy_adapter.py`:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_start_service_creates_server_and_client_instances(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].service.id == service.service_id
    assert api.clients[0].service.id == service.service_id
    assert api.servers[0].endpoint_ip == "127.0.0.1"
    assert api.clients[0].endpoint_ip == "127.0.0.1"
    assert api.servers[0].endpoint_port == 31000
    assert api.clients[0].endpoint_port == 31001
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_repeated_start_reuses_service_runtime(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.start_service(service)

    assert api.connect_started_count == 1
    assert len(api.servers) == 1
    assert len(api.clients) == 1
    assert api.servers[0].start_awaited is True


@pytest.mark.asyncio
async def test_someipy_adapter_stop_service_stops_offer_and_removes_runtime(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.stop_service(service)

    assert api.servers[0].stop_awaited is True
    assert service.service_id not in adapter._service_runtimes
```

- [ ] **Step 2: Run lifecycle tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_start_service_creates_server_and_client_instances tests/test_someipy_adapter.py::test_someipy_adapter_repeated_start_reuses_service_runtime tests/test_someipy_adapter.py::test_someipy_adapter_stop_service_stops_offer_and_removes_runtime -q
```

Expected: FAIL because `_service_runtimes` and service instance lifecycle do not exist yet.

- [ ] **Step 3: Add runtime state to `SomeipyAdapter`**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, add these imports:

```python
from dataclasses import dataclass
from types import SimpleNamespace
```

Add this import with the existing adapter imports:

```python
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
```

Add this dataclass above `class SomeipyAdapter`:

```python
@dataclass
class _SomeipyServiceRuntime:
    mapped_service: Any
    server: Any
    client: Any
    endpoint_port: int
    client_port: int
    active_eventgroups: set[int]
```

Update `SomeipyAdapter.__init__`:

```python
        self._service_runtimes: dict[int, _SomeipyServiceRuntime] = {}
        self._service_order: dict[int, int] = {}
```

- [ ] **Step 4: Implement runtime creation and service lifecycle**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, replace `start_service`, `stop_service`, and `offer_service` with:

```python
    async def start_service(self, service: ServiceDefinition) -> None:
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.start_offer())

    async def stop_service(self, service: ServiceDefinition) -> None:
        runtime = self._service_runtimes.pop(service.service_id, None)
        self._clear_service_handlers(service.service_id)
        if runtime is not None:
            await _maybe_await(runtime.server.stop_offer())

    async def offer_service(self, service: ServiceDefinition) -> None:
        await self.start_service(service)
```

Add these helper methods inside `SomeipyAdapter`:

```python
    async def _runtime_for_service(self, service: ServiceDefinition) -> _SomeipyServiceRuntime:
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            return runtime

        daemon = await self._ensure_daemon()
        api = self._api
        if api is None:
            raise RuntimeError("someipy API was not initialized")

        factory = SomeipyServiceFactory(
            api,
            method_handler_factory=self._method_handler_factory(api),
        )
        mapped_service = factory.build_service(service)
        service_index = self._service_order.setdefault(service.service_id, len(self._service_order))
        endpoint_port = self._base_port + service_index * 10
        client_port = endpoint_port + 1
        server = api.ServerServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=self._local_ip,
            endpoint_port=endpoint_port,
            ttl=int(service.deployment.offer_ttl_s),
            cyclic_offer_delay_ms=1000,
        )
        client = api.ClientServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=self._local_ip,
            endpoint_port=client_port,
            client_id=0x1000 + service_index,
        )
        client.register_callback(
            lambda event_id, payload: self._dispatch_event(service, event_id, payload)
        )
        runtime = _SomeipyServiceRuntime(
            mapped_service=mapped_service,
            server=server,
            client=client,
            endpoint_port=endpoint_port,
            client_port=client_port,
            active_eventgroups=set(),
        )
        self._service_runtimes[service.service_id] = runtime
        return runtime

    def _method_handler_factory(self, api: Any) -> Any:
        def handler_factory(service: ServiceDefinition, method_part: Any) -> Any:
            async def method_handler(input_data: bytes, addr: tuple[str, int]) -> Any:
                result_type = getattr(api, "MethodResult", None)
                result = result_type() if result_type is not None else SimpleNamespace()
                message_type = getattr(api, "MessageType", None)
                return_code = getattr(api, "ReturnCode", None)
                result.message_type = (
                    getattr(message_type, "RESPONSE", None)
                    if message_type is not None
                    else "RESPONSE"
                )
                result.return_code = (
                    getattr(return_code, "E_OK", None) if return_code is not None else "E_OK"
                )
                result.payload = input_data
                return result

            return method_handler

        return handler_factory
```

Add this module-level helper near the bottom of the file:

```python
async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
```

- [ ] **Step 5: Run lifecycle tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_start_service_creates_server_and_client_instances tests/test_someipy_adapter.py::test_someipy_adapter_repeated_start_reuses_service_runtime tests/test_someipy_adapter.py::test_someipy_adapter_stop_service_stops_offer_and_removes_runtime -q
```

Expected: PASS.

- [ ] **Step 6: Commit lifecycle implementation**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: start someipy service runtimes"
```

Expected: commit succeeds.

---

### Task 3: Implement Find, Subscribe, and Unsubscribe

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Replace Phase A find-service test**

Replace `test_someipy_adapter_find_service_returns_false_after_connecting` with:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_find_service_polls_client_availability(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [False, True]})
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    result = await adapter.find_service(service)

    assert result is True
    assert api.availability_calls[service.service_id] == 2
```

- [ ] **Step 2: Replace Phase A subscribe/unsubscribe skeleton tests**

Remove assertions that expect `NotImplementedError` from `subscribe_eventgroup` and `unsubscribe_eventgroup`. Add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_subscribes_eventgroup_with_service_ttl(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.subscribe_eventgroup(service, event.eventgroup_id)

    assert api.clients[0].subscribed_eventgroups == [
        (event.eventgroup_id, int(service.deployment.find_ttl_s))
    ]
    assert adapter._service_runtimes[service.service_id].active_eventgroups == {event.eventgroup_id}


@pytest.mark.asyncio
async def test_someipy_adapter_unsubscribes_eventgroup(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.subscribe_eventgroup(service, event.eventgroup_id)
    await adapter.unsubscribe_eventgroup(service, event.eventgroup_id)

    assert api.clients[0].unsubscribed_eventgroups == [event.eventgroup_id]
    assert adapter._service_runtimes[service.service_id].active_eventgroups == set()
```

- [ ] **Step 3: Run find and subscription tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_find_service_polls_client_availability tests/test_someipy_adapter.py::test_someipy_adapter_subscribes_eventgroup_with_service_ttl tests/test_someipy_adapter.py::test_someipy_adapter_unsubscribes_eventgroup -q
```

Expected: FAIL because `find_service` still returns `False` and subscribe/unsubscribe are still skeleton behavior.

- [ ] **Step 4: Implement availability polling and eventgroup construction**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, add constants below the existing `FIELD_SET_NOT_IMPLEMENTED` block:

```python
FIND_AVAILABILITY_ATTEMPTS = 3
FIND_AVAILABILITY_DELAY_S = 0.05
```

Replace `find_service`, `subscribe_eventgroup`, and `unsubscribe_eventgroup` with:

```python
    async def find_service(self, service: ServiceDefinition) -> bool:
        runtime = await self._runtime_for_service(service)
        for attempt in range(FIND_AVAILABILITY_ATTEMPTS):
            if bool(await _maybe_await(runtime.client.is_available())):
                return True
            if attempt < FIND_AVAILABILITY_ATTEMPTS - 1:
                await asyncio.sleep(FIND_AVAILABILITY_DELAY_S)
        return False

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        runtime = await self._runtime_for_service(service)
        eventgroup = self._eventgroup_for(service, eventgroup_id)
        await _maybe_await(
            runtime.client.subscribe_eventgroup(
                eventgroup,
                ttl_subscription_seconds=int(service.deployment.find_ttl_s),
            )
        )
        runtime.active_eventgroups.add(eventgroup_id)

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        runtime = await self._runtime_for_service(service)
        eventgroup = self._eventgroup_for(service, eventgroup_id)
        await _maybe_await(runtime.client.unsubscribe_eventgroup(eventgroup))
        runtime.active_eventgroups.discard(eventgroup_id)
```

Add this helper inside `SomeipyAdapter`:

```python
    def _eventgroup_for(self, service: ServiceDefinition, eventgroup_id: int) -> Any:
        api = self._api
        if api is None:
            raise RuntimeError("someipy API was not initialized")
        factory = SomeipyServiceFactory(api)
        events = []
        for event in service.events:
            if event.eventgroup_id == eventgroup_id:
                events.append(
                    api.Event(
                        id=event.event_id,
                        protocol=factory.protocol_for(event.transport),
                    )
                )
        for field in service.fields:
            notifier = field.notifier
            if notifier is not None and notifier.eventgroup_id == eventgroup_id:
                events.append(
                    api.Event(
                        id=notifier.element_id,
                        protocol=factory.protocol_for(notifier.transport),
                    )
                )
        if not events:
            raise ValueError(
                f"Eventgroup 0x{eventgroup_id:04X} not found in service {service.service_id_hex}"
            )
        return api.EventGroup(id=eventgroup_id, events=events)
```

- [ ] **Step 5: Run find and subscription tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_find_service_polls_client_availability tests/test_someipy_adapter.py::test_someipy_adapter_subscribes_eventgroup_with_service_ttl tests/test_someipy_adapter.py::test_someipy_adapter_unsubscribes_eventgroup -q
```

Expected: PASS.

- [ ] **Step 6: Commit find and subscription implementation**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: support someipy eventgroup subscriptions"
```

Expected: commit succeeds.

---

### Task 4: Publish Events and Dispatch Received Event Callbacks

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Replace Phase A publish skeleton test**

Remove the `publish_event` `NotImplementedError` expectation from `test_someipy_adapter_protocol_actions_raise_not_implemented`. Add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_publish_event_sends_payload(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)

    await adapter.publish_event(service, event, b"\x41\x48\x00\x00\x42\xc6\x80\x00")

    assert api.servers[0].sent_events == [
        (event.eventgroup_id, event.event_id, b"\x41\x48\x00\x00\x42\xc6\x80\x00")
    ]
```

- [ ] **Step 2: Add callback dispatch test**

Add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_dispatches_received_event_to_registered_handlers(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    received = []

    await adapter.register_event_handler(service, event, received.append)
    await adapter.subscribe_eventgroup(service, event.eventgroup_id)
    await adapter.publish_event(service, event, b"\x01\x02\x03\x04")

    assert len(received) == 1
    assert received[0].service_id == service.service_id
    assert received[0].element_id == event.event_id
    assert received[0].eventgroup_id == event.eventgroup_id
    assert received[0].payload == b"\x01\x02\x03\x04"
```

- [ ] **Step 3: Run publish and callback tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_publish_event_sends_payload tests/test_someipy_adapter.py::test_someipy_adapter_dispatches_received_event_to_registered_handlers -q
```

Expected: FAIL because `publish_event` still raises and `_dispatch_event` does not exist.

- [ ] **Step 4: Implement event publish and callback dispatch**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, replace `publish_event` with:

```python
    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        if event.eventgroup_id is None:
            raise ValueError(f"Event {event.name!r} has no eventgroup id")
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.send_event(event.eventgroup_id, event.event_id, payload))
```

Add this helper inside `SomeipyAdapter`:

```python
    def _dispatch_event(
        self,
        service: ServiceDefinition,
        event_id: int,
        payload: bytes,
    ) -> None:
        eventgroup_id = self._eventgroup_id_for_element(service, event_id)
        adapter_event = AdapterEvent(
            service_id=service.service_id,
            element_id=event_id,
            eventgroup_id=eventgroup_id,
            payload=payload,
        )
        for handler in list(self._event_handlers.get((service.service_id, event_id), [])):
            handler(adapter_event)

    def _eventgroup_id_for_element(
        self,
        service: ServiceDefinition,
        element_id: int,
    ) -> int | None:
        for event in service.events:
            if event.event_id == element_id:
                return event.eventgroup_id
        for field in service.fields:
            notifier = field.notifier
            if notifier is not None and notifier.element_id == element_id:
                return notifier.eventgroup_id
        return None
```

- [ ] **Step 5: Run publish and callback tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_publish_event_sends_payload tests/test_someipy_adapter.py::test_someipy_adapter_dispatches_received_event_to_registered_handlers -q
```

Expected: PASS.

- [ ] **Step 6: Commit event publish implementation**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: publish someipy events through adapter"
```

Expected: commit succeeds.

---

### Task 5: Implement Field Getter and Notifier Paths

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Replace field getter skeleton test**

Replace `test_someipy_adapter_field_get_returns_unimplemented_error_with_getter` with:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_field_get_calls_getter_method_and_returns_payload(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]

    result = await adapter.field_get(service, field, b"\x07")

    assert result.status == "success"
    assert result.detail == "someipy field getter completed"
    assert result.payload == b"\x07"
    assert api.connect_started_count == 1
```

- [ ] **Step 2: Replace field notifier skeleton test**

Remove the `field_notify` `NotImplementedError` expectation from `test_someipy_adapter_protocol_actions_raise_not_implemented`. Add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_field_notify_sends_notifier_event(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None

    await adapter.field_notify(service, field, b"\x09")

    assert api.servers[0].sent_events == [
        (field.notifier.eventgroup_id, field.notifier.element_id, b"\x09")
    ]
```

- [ ] **Step 3: Add field notifier callback dispatch test**

Add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_dispatches_field_notifier_to_registered_handlers(adc40_soc_dir) -> None:
    api = FakeSomeipyApi()
    adapter = SomeipyAdapter(api=api, local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None
    assert field.notifier.eventgroup_id is not None
    received = []

    await adapter.register_field_notifier_handler(service, field, received.append)
    await adapter.subscribe_eventgroup(service, field.notifier.eventgroup_id)
    await adapter.field_notify(service, field, b"\x01")

    assert len(received) == 1
    assert received[0].service_id == service.service_id
    assert received[0].element_id == field.notifier.element_id
    assert received[0].eventgroup_id == field.notifier.eventgroup_id
    assert received[0].payload == b"\x01"
```

- [ ] **Step 4: Run field tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_field_get_calls_getter_method_and_returns_payload tests/test_someipy_adapter.py::test_someipy_adapter_field_notify_sends_notifier_event tests/test_someipy_adapter.py::test_someipy_adapter_dispatches_field_notifier_to_registered_handlers -q
```

Expected: FAIL because field getter and notifier still use skeleton behavior.

- [ ] **Step 5: Implement method result mapping, field getter, and field notifier**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, replace `field_get`, `field_notify`, and the non-FF branch of `call_method` with:

```python
    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        runtime = await self._runtime_for_service(service)
        result = await _maybe_await(runtime.client.call_method(method.method_id, payload))
        return self._adapter_method_result(result, "someipy method call completed")

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no getter")
        runtime = await self._runtime_for_service(service)
        result = await _maybe_await(runtime.client.call_method(field.getter.element_id, payload))
        return self._adapter_method_result(result, "someipy field getter completed")

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        if field.notifier.eventgroup_id is None:
            raise ValueError(f"Field {field.name!r} notifier has no eventgroup id")
        runtime = await self._runtime_for_service(service)
        await _maybe_await(
            runtime.server.send_event(
                field.notifier.eventgroup_id,
                field.notifier.element_id,
                payload,
            )
        )
```

Add this helper inside `SomeipyAdapter`:

```python
    def _adapter_method_result(self, result: Any, success_detail: str) -> AdapterMethodResult:
        payload = getattr(result, "payload", None)
        return_code = getattr(result, "return_code", None)
        return_code_name = getattr(return_code, "name", None) or str(return_code)
        if return_code_name not in {"E_OK", "ReturnCode.E_OK"}:
            return AdapterMethodResult(
                status="error",
                detail=f"someipy method returned {return_code_name}",
                payload=payload if isinstance(payload, bytes) else None,
            )
        if payload is not None and not isinstance(payload, bytes):
            return AdapterMethodResult(
                status="error",
                detail=f"someipy method payload must be bytes, got {type(payload).__name__}",
            )
        return AdapterMethodResult(status="success", detail=success_detail, payload=payload)
```

- [ ] **Step 6: Run field tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_field_get_calls_getter_method_and_returns_payload tests/test_someipy_adapter.py::test_someipy_adapter_field_notify_sends_notifier_event tests/test_someipy_adapter.py::test_someipy_adapter_dispatches_field_notifier_to_registered_handlers -q
```

Expected: PASS.

- [ ] **Step 7: Commit field implementation**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: support someipy field runtime operations"
```

Expected: commit succeeds.

---

### Task 6: Add Optional someipyd Process Ownership

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Modify: `tests/test_someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Add daemon ownership test**

Add this test to `tests/test_someipy_adapter.py`:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_can_own_someipyd_process(adc40_soc_dir, monkeypatch, tmp_path) -> None:
    api = FakeSomeipyApi()
    started = []
    stopped = []

    class FakeProcess:
        def stop(self) -> None:
            stopped.append(True)

    def fake_start(config, work_dir):
        started.append((config, work_dir))
        return FakeProcess()

    monkeypatch.setattr("someip_gui_tool.adapters.someipy_adapter.SomeipydProcess.start", fake_start)
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        start_daemon=True,
        daemon_work_dir=tmp_path,
    )
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    await adapter.start_service(service)
    await adapter.shutdown()

    assert len(started) == 1
    assert started[0][0].interface == "127.0.0.1"
    assert started[0][0].tcp_host == "127.0.0.1"
    assert started[0][0].tcp_port == 31000
    assert started[0][1] == tmp_path
    assert stopped == [True]
```

- [ ] **Step 2: Run daemon ownership test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_can_own_someipyd_process -q
```

Expected: FAIL because `SomeipyAdapter.__init__` does not accept `start_daemon` or `daemon_work_dir`.

- [ ] **Step 3: Implement optional daemon ownership**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, add imports:

```python
import tempfile
from pathlib import Path
```

Change the daemon import to:

```python
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess
```

Update `SomeipyAdapter.__init__` signature:

```python
        start_daemon: bool = False,
        daemon_work_dir: Path | None = None,
```

Add these attributes in `__init__`:

```python
        self._start_daemon = start_daemon
        self._daemon_work_dir = daemon_work_dir
        self._owned_daemon_process: SomeipydProcess | None = None
        self._owned_temp_dir: tempfile.TemporaryDirectory[str] | None = None
```

Add this helper inside `SomeipyAdapter`:

```python
    def _stop_owned_daemon_process(self) -> None:
        if self._owned_daemon_process is not None:
            self._owned_daemon_process.stop()
            self._owned_daemon_process = None
        if self._owned_temp_dir is not None:
            self._owned_temp_dir.cleanup()
            self._owned_temp_dir = None
```

At the start of `_ensure_daemon`, inside the lock and before `connect_to_someipy_daemon`, add:

```python
            if self._start_daemon and self._owned_daemon_process is None:
                work_dir = self._daemon_work_dir
                if work_dir is None:
                    self._owned_temp_dir = tempfile.TemporaryDirectory(prefix="someipyd-adapter-")
                    work_dir = Path(self._owned_temp_dir.name)
                config = SomeipydConfig(
                    interface=self._local_ip,
                    tcp_host=self._local_ip,
                    tcp_port=self._base_port,
                )
                self._owned_daemon_process = SomeipydProcess.start(
                    config=config,
                    work_dir=work_dir,
                )
```

Replace the final daemon connection assignment in `_ensure_daemon` with:

```python
            try:
                self._daemon = await api.connect_to_someipy_daemon(config)
            except Exception:
                self._stop_owned_daemon_process()
                raise
            return self._daemon
```

Update `shutdown` so owned process cleanup runs even when no daemon object is currently connected:

```python
    async def shutdown(self) -> None:
        async with self._daemon_lock:
            daemon = self._daemon
            self._daemon = None
            self._service_runtimes.clear()
            self._event_handlers.clear()
            try:
                if daemon is not None:
                    disconnect = getattr(daemon, "disconnect_from_daemon", None)
                    if disconnect is not None:
                        result = disconnect()
                        if inspect.isawaitable(result):
                            await result
            finally:
                self._stop_owned_daemon_process()
```

- [ ] **Step 4: Run daemon ownership test**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_can_own_someipyd_process -q
```

Expected: PASS.

- [ ] **Step 5: Commit daemon ownership**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "feat: allow adapter-owned someipyd process"
```

Expected: commit succeeds.

---

### Task 7: Clean Up Skeleton Assertions and Verify Adapter Behavior

**Files:**
- Modify: `tests/test_someipy_adapter.py`
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Remove Phase A skeleton constants and tests**

In `src/someip_gui_tool/adapters/someipy_adapter.py`, remove:

```python
FIELD_GET_NOT_IMPLEMENTED = (
    "someipy field getter execution is not implemented in Phase A adapter skeleton"
)
FIELD_SET_NOT_IMPLEMENTED = (
    "someipy field setter execution is not implemented in Phase A adapter skeleton"
)
```

In `tests/test_someipy_adapter.py`, remove tests that assert this text:

```python
"not implemented in Phase A adapter skeleton"
```

Keep `test_someipy_adapter_field_set_returns_error_without_setter`.

- [ ] **Step 2: Add non-OK method result test**

Add this test to `tests/test_someipy_adapter.py`:

```python
def test_someipy_adapter_maps_non_ok_method_result_to_error() -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=31000)
    result = adapter._adapter_method_result(
        type("Result", (), {"return_code": "E_NOT_OK", "payload": b"\x01"})(),
        "success detail",
    )

    assert result.status == "error"
    assert "E_NOT_OK" in result.detail
    assert result.payload == b"\x01"
```

- [ ] **Step 3: Add FF method limitation regression test if it was changed**

Keep this test passing:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_reports_ff_method_limited(adc40_soc_dir) -> None:
    adapter = SomeipyAdapter(api=FakeSomeipyApi(), local_ip="127.0.0.1", base_port=31000)
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    result = await adapter.call_method(service, service.methods[0], b"\x01")

    assert result.status == "limited"
    assert "fire-and-forget" in result.detail
```

- [ ] **Step 4: Run all adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit cleanup**

Run:

```bash
git add src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
git commit -m "test: verify someipy adapter phase b behavior"
```

Expected: commit succeeds.

---

### Task 8: Final Verification and Phase B Summary

**Files:**
- Modify: `docs/superpowers/plans/2026-05-16-mvp1-someipy-adapter-phase-b.md` only if command corrections are discovered during execution.
- Test: full suite and spike scripts.

- [ ] **Step 1: Run all tests with Qt offscreen**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run dry protocol spike**

Run:

```bash
.venv/bin/python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode dry-run
```

Expected output includes:

```text
Spike report: someipy-protocol-spike-dry-run
PASS udp-ff-method
PASS tcp-method
PASS udp-event
PASS tcp-event
PASS field-getter-notifier
```

- [ ] **Step 3: Run real protocol spike with daemon autostart**

Run:

```bash
PATH=/Users/lanyy/Code/someip/.venv/bin:$PATH .venv/bin/python scripts/run_protocol_spike.py --definition-root ADC40_SOC --mode real --local-ip 127.0.0.1 --base-port 30500 --start-daemon
```

Expected output includes:

```text
Spike report: someipy-protocol-spike-real-run
PASS someipy-api
PASS someipyd
SKIP udp-ff-method
SKIP tcp-method
PASS udp-event
PASS tcp-event
PASS field-getter-notifier
```

If this command fails with `Operation not permitted` inside the sandbox, rerun it with sandbox escalation because it needs localhost daemon networking.

- [ ] **Step 4: Run adapter-owned daemon smoke through unit boundary**

Run:

```bash
.venv/bin/python -m pytest tests/test_someipy_adapter.py::test_someipy_adapter_can_own_someipyd_process -q
```

Expected: PASS.

- [ ] **Step 5: Check no skeleton wording remains in production adapter**

Run:

```bash
rg -n "Phase A adapter skeleton|not implemented in Phase A|FIELD_GET_NOT_IMPLEMENTED|FIELD_SET_NOT_IMPLEMENTED" src/someip_gui_tool/adapters/someipy_adapter.py tests/test_someipy_adapter.py
```

Expected: no matches.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes except local environment or intentionally generated artifacts.

---

## Self-Review

Spec coverage:

- Adapter boundary remains the only layer using `someipy`.
- Real event subscribe, unsubscribe, publish, and callback behavior are covered.
- Field getter and notifier behavior are covered.
- FF method limitation remains explicit.
- Trace and log behavior remain Core responsibilities and continue to be tested through `RuntimeSession` with mock adapter tests.
- GUI wiring is intentionally excluded so this plan stays independently testable.

Placeholder scan:

- This plan contains concrete file paths, concrete tests, concrete implementation snippets, exact commands, and exact expected outcomes.
- No task relies on a named but undefined helper; helper types are created in Task 1 before use.

Type consistency:

- `SomeipyAdapter` keeps the existing `SomeIpAdapter` method signatures.
- `AdapterMethodResult` and `AdapterEvent` remain the adapter/core data boundary.
- `SomeipyServiceFactory.protocol_for()` is used for protocol mapping instead of private helpers.
