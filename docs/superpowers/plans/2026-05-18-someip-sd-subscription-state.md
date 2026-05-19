# SOME/IP-SD Subscription State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Client event Subscribe/Unsubscribe behavior align with SOME/IP-SD state semantics without claiming protocol states the application cannot observe.

**Architecture:** Split service discovery from subscription intent. The runtime will track service availability and local subscription request state, while adapters expose whether a service is known available separately from actively sending `FindService`. Subscribe may request discovery when the service is not yet known, but GUI logs will remain explicit that subscription is requested/pending until protocol evidence exists.

**Tech Stack:** Python 3.11, PySide runtime session, `someipy` adapter, pytest, pytest-qt.

---

## Protocol Basis

Use AUTOSAR SOME/IP-SD semantics as the authority:

- Service discovery locates a service instance and obtains endpoint information. A client can either receive periodic `OfferService` or send `FindService` and wait for `OfferService`.
- Eventgroup pub/sub is tied to service availability. The server-side state diagram has `Service Down` / `Service Up`, and subscription transitions happen inside `Service Up`.
- `SubscribeEventgroup` moves `Not Subscribed` to `Subscribed` only when the server accepts it and sends `SubscribeEventgroupAck`.
- `StopSubscribeEventgroup` is meaningful from a previously subscribed state; for multicast/adaptive cases subscription counters may affect whether events are disabled.

Current implementation gap:

- `RuntimeSession.subscribe_event()` calls `adapter.find_service()` unconditionally before every subscribe. This is protocol-legal as a discovery refresh, but it conflates two actions: service discovery and subscription.
- `subscribe_eventgroup()` only tells local `someipyd` to request/queue a subscription. It cannot prove the wire `SubscribeEventgroup` was sent or ACKed.
- `unsubscribe_eventgroup()` only tells local `someipyd` to cancel a request/subscription. It cannot prove a wire `StopSubscribeEventgroup` was sent.

Target behavior:

- `Client Start` performs explicit service discovery: send `FindService`, poll for availability.
- `Subscribe` checks cached availability first. If unavailable, it may request discovery once and records the subscription as pending.
- `Subscribe` always logs request state, never ACK state, unless an ACK observation is implemented later.
- `Unsubscribe` logs request/cancel state, never claims wire `StopSubscribeEventgroup` occurred unless the adapter can prove it.

References:

- AUTOSAR SOME/IP Service Discovery Protocol Specification R23-11, Publish/Subscribe state diagrams and transitions for `SubscribeEventgroup`, `SubscribeEventgroupAck`, `StopSubscribeEventgroup`.
- someipy Service Discovery docs: SD locates service instances; subscribers send Subscribe entries with client endpoint; servers respond with subscribe acknowledge.

## File Structure

- Modify `src/someip_gui_tool/adapters/base.py`
  - Add explicit adapter result models for availability and subscription request outcomes.
  - Add an adapter method for checking local service availability without sending wire `FindService`.

- Modify `src/someip_gui_tool/adapters/mock.py`
  - Implement the new adapter method and return structured subscription request results.
  - Keep existing fake event delivery behavior.

- Modify `src/someip_gui_tool/adapters/someipy_adapter.py`
  - Refactor current `find_service()` into “send FindService” plus “poll local availability”.
  - Implement a no-Find availability check for subscribe decisions.
  - Return structured subscription/unsubscription request results.

- Modify `src/someip_gui_tool/core/runtime_session.py`
  - Track service availability per service.
  - Track local eventgroup subscription request state per `(service_id, eventgroup_id)`.
  - Replace unconditional subscribe-time `find_service()` with a protocol-aware discovery refresh flow.
  - Log requested/pending/cancelled-local states accurately.

- Modify `tests/test_someipy_adapter.py`
  - Add tests proving availability check does not send wire `FindService`.
  - Keep tests proving explicit `find_service()` does send wire `FindService`.

- Modify `tests/test_runtime_session.py`
  - Add tests for Start discovery, Subscribe with available service, Subscribe pending when unavailable, and Unsubscribe with/without local request state.

- Modify `tests/test_gui_smoke.py`
  - Update UI assertions to look for protocol-accurate request/pending text.

- Modify `README.md` and protocol verification docs if their expected run-log text still says `Subscribed` or `Unsubscribed`.

## Task 1: Add Adapter Result Models

**Files:**
- Modify: `src/someip_gui_tool/adapters/base.py`
- Test: none yet; this supports later tests.

- [ ] **Step 1: Add dataclasses for availability and subscription results**

Insert after `AdapterEvent`:

```python
@dataclass(frozen=True)
class AdapterServiceAvailability:
    available: bool
    detail: str


@dataclass(frozen=True)
class AdapterSubscriptionResult:
    status: str
    detail: str
    service_available: bool | None = None
```

Use these status strings:

```python
SUBSCRIPTION_REQUESTED = "requested"
SUBSCRIPTION_PENDING = "pending"
SUBSCRIPTION_CANCEL_REQUESTED = "cancel-requested"
SUBSCRIPTION_NOT_REQUESTED = "not-requested"
```

- [ ] **Step 2: Add a local availability method to `SomeIpAdapter`**

Add to the abstract class after `find_service()`:

```python
@abstractmethod
async def check_service_available(self, service: ServiceDefinition) -> AdapterServiceAvailability:
    raise NotImplementedError
```

- [ ] **Step 3: Change subscription method return types**

Change abstract signatures:

```python
@abstractmethod
async def subscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    raise NotImplementedError

@abstractmethod
async def unsubscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    raise NotImplementedError
```

- [ ] **Step 4: Run interface type smoke**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_mock_adapter.py::test_mock_adapter_records_calls_for_basic_operations
```

Expected: FAIL because concrete adapters have not implemented the new abstract method and return values yet.

## Task 2: Implement Mock Adapter Behavior

**Files:**
- Modify: `src/someip_gui_tool/adapters/mock.py`
- Test: `tests/test_mock_adapter.py`

- [ ] **Step 1: Write failing tests for mock subscription results**

Add to `tests/test_mock_adapter.py`:

```python
@pytest.mark.asyncio
async def test_mock_adapter_reports_service_availability(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    adapter = MockSomeIpAdapter()

    result = await adapter.check_service_available(service)

    assert result.available is True
    assert result.detail == "mock service is available"


@pytest.mark.asyncio
async def test_mock_adapter_subscription_results_are_request_states(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = MockSomeIpAdapter()

    subscribe_result = await adapter.subscribe_eventgroup(service, event.eventgroup_id or 0)
    unsubscribe_result = await adapter.unsubscribe_eventgroup(service, event.eventgroup_id or 0)

    assert subscribe_result.status == "requested"
    assert subscribe_result.service_available is True
    assert unsubscribe_result.status == "cancel-requested"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_mock_adapter.py -k "availability or subscription_results"
```

Expected: FAIL because `MockSomeIpAdapter.check_service_available` and result returns are missing.

- [ ] **Step 3: Implement mock adapter methods**

Update imports in `src/someip_gui_tool/adapters/mock.py`:

```python
from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterServiceAvailability,
    AdapterStartConfig,
    AdapterSubscriptionResult,
    EventHandler,
    SomeIpAdapter,
)
```

Add:

```python
async def check_service_available(self, service: ServiceDefinition) -> AdapterServiceAvailability:
    self.calls.append(AdapterCall("check_service_available", {"service_id": service.service_id_hex}))
    return AdapterServiceAvailability(available=True, detail="mock service is available")
```

Update `subscribe_eventgroup`:

```python
async def subscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    self.calls.append(
        AdapterCall(
            "subscribe_eventgroup",
            {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
        )
    )
    self._subscribed_eventgroups.add((service.service_id, eventgroup_id))
    return AdapterSubscriptionResult(
        status="requested",
        detail="mock subscription request accepted",
        service_available=True,
    )
```

Update `unsubscribe_eventgroup`:

```python
async def unsubscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    self.calls.append(
        AdapterCall(
            "unsubscribe_eventgroup",
            {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
        )
    )
    self._subscribed_eventgroups.discard((service.service_id, eventgroup_id))
    return AdapterSubscriptionResult(
        status="cancel-requested",
        detail="mock unsubscribe request accepted",
        service_available=True,
    )
```

- [ ] **Step 4: Run mock adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_mock_adapter.py
```

Expected: PASS.

## Task 3: Split someipy FindService From Availability Check

**Files:**
- Modify: `src/someip_gui_tool/adapters/someipy_adapter.py`
- Test: `tests/test_someipy_adapter.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_someipy_adapter.py`:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_check_service_available_does_not_send_sd_find(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [True]})
    sent_packets: list[tuple[bytes, tuple[str, int]]] = []
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        sd_socket_factory=lambda: _FakeSdSocket(sent_packets),
    )

    result = await adapter.check_service_available(service)

    assert result.available is True
    assert sent_packets == []
    assert api.availability_calls[service.service_id] == 1


@pytest.mark.asyncio
async def test_someipy_adapter_subscribe_result_is_pending_when_service_unavailable(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    assert event.eventgroup_id is not None
    api = FakeSomeipyApi(availability_sequences={service.service_id: [False]})
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        sd_socket_factory=_FakeSdSocket,
    )

    result = await adapter.subscribe_eventgroup(service, event.eventgroup_id)

    assert result.status == "pending"
    assert result.service_available is False
    assert api.clients[0].subscribed_eventgroups == [
        (event.eventgroup_id, int(service.deployment.find_ttl_s))
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_someipy_adapter.py -k "check_service_available or subscribe_result_is_pending"
```

Expected: FAIL because the new adapter method/result behavior is missing.

- [ ] **Step 3: Implement availability polling helper**

Update imports in `someipy_adapter.py`:

```python
from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterServiceAvailability,
    AdapterStartConfig,
    AdapterSubscriptionResult,
    EventHandler,
    SomeIpAdapter,
)
```

Add helper:

```python
async def _poll_service_available(
    self,
    service: ServiceDefinition,
    *,
    attempts: int,
) -> bool:
    runtime = await self._runtime_for_service(service)
    for attempt in range(attempts):
        if bool(await _maybe_await(runtime.client.is_available())):
            return True
        if attempt < attempts - 1:
            await asyncio.sleep(FIND_AVAILABILITY_DELAY_S)
    return False
```

Update `find_service()`:

```python
async def find_service(self, service: ServiceDefinition) -> bool:
    runtime = await self._runtime_for_service(service)
    self._send_find_service_request(service, runtime)
    return await self._poll_service_available(
        service,
        attempts=FIND_AVAILABILITY_ATTEMPTS,
    )
```

Add:

```python
async def check_service_available(self, service: ServiceDefinition) -> AdapterServiceAvailability:
    available = await self._poll_service_available(service, attempts=1)
    return AdapterServiceAvailability(
        available=available,
        detail=(
            "someipy service is available in daemon cache"
            if available
            else "someipy service is not available in daemon cache"
        ),
    )
```

- [ ] **Step 4: Return structured subscribe/unsubscribe results**

Update `subscribe_eventgroup()`:

```python
async def subscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    availability = await self.check_service_available(service)
    runtime = await self._runtime_for_service(service)
    eventgroup = self._eventgroup_for(service, eventgroup_id)
    await _maybe_await(
        runtime.client.subscribe_eventgroup(
            eventgroup,
            ttl_subscription_seconds=int(runtime.find_ttl_s),
        )
    )
    runtime.active_eventgroups.add(eventgroup_id)
    return AdapterSubscriptionResult(
        status="requested" if availability.available else "pending",
        detail=(
            "someipy subscription request submitted; service available"
            if availability.available
            else "someipy subscription request queued pending service availability"
        ),
        service_available=availability.available,
    )
```

Update `unsubscribe_eventgroup()`:

```python
async def unsubscribe_eventgroup(
    self,
    service: ServiceDefinition,
    eventgroup_id: int,
) -> AdapterSubscriptionResult:
    availability = await self.check_service_available(service)
    runtime = await self._runtime_for_service(service)
    eventgroup = self._eventgroup_for(service, eventgroup_id)
    was_requested = eventgroup_id in runtime.active_eventgroups
    await _maybe_await(runtime.client.unsubscribe_eventgroup(eventgroup))
    runtime.active_eventgroups.discard(eventgroup_id)
    return AdapterSubscriptionResult(
        status="cancel-requested" if was_requested else "not-requested",
        detail=(
            "someipy unsubscribe request submitted"
            if was_requested
            else "someipy unsubscribe requested without a local subscription request"
        ),
        service_available=availability.available,
    )
```

- [ ] **Step 5: Run someipy adapter tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_someipy_adapter.py
```

Expected: PASS. Existing tests may need assertion updates from `None` returns to structured results.

## Task 4: Make Runtime Session State Protocol-Aware

**Files:**
- Modify: `src/someip_gui_tool/core/runtime_session.py`
- Test: `tests/test_runtime_session.py`

- [ ] **Step 1: Write failing tests for protocol-aware subscribe**

Add to `tests/test_runtime_session.py`:

```python
class AvailabilityAdapter(MockSomeIpAdapter):
    def __init__(self, available_sequence):
        super().__init__()
        self.available_sequence = list(available_sequence)

    async def check_service_available(self, service):
        from someip_gui_tool.adapters.base import AdapterServiceAvailability

        available = self.available_sequence.pop(0) if self.available_sequence else False
        self.calls.append(
            type(self.calls[0])(
                "check_service_available",
                {"service_id": service.service_id_hex, "available": available},
            )
            if self.calls
            else __import__("someip_gui_tool.adapters.mock", fromlist=["AdapterCall"]).AdapterCall(
                "check_service_available",
                {"service_id": service.service_id_hex, "available": available},
            )
        )
        return AdapterServiceAvailability(available=available, detail="test availability")


@pytest.mark.asyncio
async def test_runtime_session_subscribe_does_not_find_when_service_already_available(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = AvailabilityAdapter([True])
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.CLIENT))
    await session.subscribe_event(service, event)

    subscribe_slice = [call.name for call in adapter.calls[-2:]]
    assert subscribe_slice == ["check_service_available", "subscribe_eventgroup"]
    assert "pending" not in session.run_log[-1].message.lower()


@pytest.mark.asyncio
async def test_runtime_session_subscribe_requests_discovery_when_service_unavailable(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    event = service.events[0]
    adapter = AvailabilityAdapter([False, False])
    session = RuntimeSession(adapter=adapter)

    await session.start_service(service, _valid_config(service, Role.CLIENT))
    await session.subscribe_event(service, event)

    call_names = [call.name for call in adapter.calls]
    assert call_names.count("find_service") == 2
    assert session.problems[-1].code == "subscription_pending_service_unavailable"
```

When implementing, simplify `AvailabilityAdapter` if the import expression is too noisy; the important assertion is call order.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_session.py -k "subscribe_does_not_find or subscribe_requests_discovery"
```

Expected: FAIL because current `subscribe_event()` unconditionally calls `find_service()`.

- [ ] **Step 3: Add runtime state fields**

In `RuntimeSession.__init__`, add:

```python
self._service_availability: dict[int, bool] = {}
self._subscription_requests: set[tuple[int, int]] = set()
```

In `start_service()`, when client `find_service()` returns:

```python
self._service_availability[service.service_id] = found
```

In `stop_service()`, clear:

```python
self._service_availability.pop(service.service_id, None)
self._subscription_requests = {
    key for key in self._subscription_requests if key[0] != service.service_id
}
```

- [ ] **Step 4: Replace unconditional subscribe-time find**

Replace the start of `subscribe_event()` after eventgroup validation:

```python
availability = await self.adapter.check_service_available(service)
found = availability.available
if not found:
    found = await self.adapter.find_service(service)
self._service_availability[service.service_id] = found
```

Keep the existing pending warning, but only emit it when `found` is false.

After adapter subscribe succeeds:

```python
self._subscription_requests.add((service.service_id, event.eventgroup_id))
```

When logging, use:

```python
message = (
    f"Requested subscription for eventgroup 0x{event.eventgroup_id:04X} for {event.name}"
)
if not found:
    message += " (pending service availability)"
self._log("info", "Core", message, service_id=service.service_id_hex, element_id=event.event_id_hex)
```

- [ ] **Step 5: Make unsubscribe state-aware**

At the start of `unsubscribe_event()` after eventgroup validation:

```python
subscription_key = (service.service_id, event.eventgroup_id)
was_requested = subscription_key in self._subscription_requests
if not was_requested:
    warning = (
        f"Unsubscribe requested for eventgroup 0x{event.eventgroup_id:04X} "
        f"for {event.name}, but no local subscription request is active."
    )
    self.problems.append(
        RuntimeProblem(
            code="unsubscribe_without_local_subscription",
            severity="warning",
            message=warning,
            service_id=service.service_id,
        )
    )
    self._log(
        "warning",
        "Core",
        warning,
        service_id=service.service_id_hex,
        element_id=event.event_id_hex,
        error_detail="unsubscribe_without_local_subscription",
    )
```

After adapter unsubscribe succeeds:

```python
self._subscription_requests.discard(subscription_key)
```

Keep info log:

```python
f"Requested unsubscribe for eventgroup 0x{event.eventgroup_id:04X} for {event.name}"
```

- [ ] **Step 6: Run runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_runtime_session.py
```

Expected: PASS after updating older call-order assertions.

## Task 5: Update GUI Text Assertions and User-Facing Docs

**Files:**
- Modify: `tests/test_gui_smoke.py`
- Modify: `README.md`
- Modify: `docs/mvp1-gui-real-someip-manual-verification-zh.md`
- Modify: `docs/mvp1-autosar-someip-compliance-verification-zh.md`

- [ ] **Step 1: Update GUI tests**

Replace assertions expecting:

```text
Subscribed eventgroup
Unsubscribed eventgroup
```

with:

```text
Requested subscription for eventgroup
Requested unsubscribe for eventgroup
```

Add one smoke assertion for pending text when the mock adapter reports unavailable if the GUI already has a suitable injection path. If not, keep this at runtime-session coverage.

- [ ] **Step 2: Update README behavior wording**

In `README.md`, replace client subscribe expectations with:

```text
Run Log shows "Requested subscription for eventgroup ...".
If the service is not available yet, Run Log also shows a pending warning.
Wireshark should show SubscribeEventgroup only after someipyd has discovered the server OfferService.
```

For unsubscribe:

```text
Run Log shows "Requested unsubscribe for eventgroup ...".
Wireshark shows StopSubscribeEventgroup only when there was an active subscription known to someipyd.
```

- [ ] **Step 3: Update verification docs**

In protocol verification docs, keep Wireshark as the final criterion:

```text
GUI "Requested subscription" proves only local request submission.
Protocol pass requires captured SubscribeEventgroup and matching SubscribeEventgroupAck.
GUI "Requested unsubscribe" proves only local cancel submission.
Protocol pass requires captured StopSubscribeEventgroup when a subscription was active.
```

- [ ] **Step 4: Run GUI and docs-adjacent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_smoke.py tests\test_runtime_session.py
```

Expected: PASS.

## Task 6: Add Regression Tests for Wire-Intent Boundaries

**Files:**
- Modify: `tests/test_someipy_adapter.py`
- Modify: `tests/test_runtime_session.py`

- [ ] **Step 1: Verify explicit Start Find still sends SD Find**

Keep or add:

```python
@pytest.mark.asyncio
async def test_someipy_adapter_find_service_sends_sd_find_before_polling(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    api = FakeSomeipyApi(availability_sequences={service.service_id: [False]})
    sent_packets: list[tuple[bytes, tuple[str, int]]] = []
    adapter = SomeipyAdapter(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
        sd_socket_factory=lambda: _FakeSdSocket(sent_packets),
    )

    await adapter.start_service(service, _adapter_start_config(Role.CLIENT))
    result = await adapter.find_service(service)

    assert result is False
    assert len(sent_packets) == 1
    assert sent_packets[0][1] == ("239.192.255.251", 30490)
```

- [ ] **Step 2: Verify subscribe availability check does not send SD Find when already available**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_someipy_adapter.py -k "find_service_sends_sd_find or check_service_available_does_not_send"
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Expected: all tests pass.

## Acceptance Criteria

- Client Start still emits `FindService` in real SOME/IP mode.
- Subscribe no longer unconditionally emits `FindService` if the service is already known available.
- Subscribe can request discovery when service is unavailable, but logs this as discovery/pending, not as successful subscription.
- Subscribe Run Log never claims ACK unless ACK observation is implemented.
- Unsubscribe Run Log never claims wire `StopSubscribeEventgroup` unless the adapter can prove it.
- Wireshark remains the final pass/fail criterion for `SubscribeEventgroup`, `SubscribeEventgroupAck`, and `StopSubscribeEventgroup`.
- `python -m pytest` passes.

## Self-Review

- Spec coverage: The plan covers service availability, Subscribe request/ACK semantics, StopSubscribe semantics, GUI logging, docs, and tests.
- Placeholder scan: No implementation step says “TODO” or “fill in later”; code snippets are concrete.
- Type consistency: New adapter result types are introduced before adapter/runtime use.
