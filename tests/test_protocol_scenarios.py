from dataclasses import replace
from types import SimpleNamespace

import pytest

from someip_gui_tool.adapters.someipy_api import SomeipyApiStatus
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.domain.models import FieldDefinition
from someip_gui_tool.spike.result import SpikeStatus
from someip_gui_tool.spike.runner import ProtocolSpikeRunner
from someip_gui_tool.spike.scenarios import ProtocolScenario, ScenarioKind, build_scenarios


def test_builds_required_scenarios(adc40_soc_dir):
    scenarios = build_scenarios(adc40_soc_dir)

    assert [scenario.kind for scenario in scenarios] == [
        ScenarioKind.UDP_FF_METHOD,
        ScenarioKind.TCP_METHOD,
        ScenarioKind.UDP_EVENT,
        ScenarioKind.TCP_EVENT,
        ScenarioKind.FIELD_GETTER_NOTIFIER,
    ]
    assert [scenario.service.service_id for scenario in scenarios] == [
        0x080D,
        0x0F01,
        0x080E,
        0x080A,
        0x080C,
    ]
    assert scenarios[0].method is not None
    assert scenarios[0].method.name == "SecondStartCtrl"
    assert scenarios[0].payload_values == {"SecondStartCtrlCmd": 1}
    assert scenarios[1].method is not None
    assert scenarios[1].method.name == "AudioRecPopupReq"
    assert scenarios[1].payload_values == {"AudioRecPopup": 1}
    assert scenarios[2].event is not None
    assert scenarios[2].event.name == "VehicleInfo"
    assert scenarios[2].payload_values == {
        "VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}
    }
    assert scenarios[3].event is not None
    assert scenarios[3].event.name == "IntellgntSwtDecoupSts"
    assert scenarios[3].payload_values == {"IntellgntSwtDecoupSts": [1, 2, 3]}
    assert scenarios[4].field is not None
    assert scenarios[4].field.name == "VertHeiRmdSts"
    assert scenarios[4].field.getter is not None
    assert scenarios[4].field.getter.element_id == 0x1001
    assert scenarios[4].field.notifier is not None
    assert scenarios[4].field.notifier.element_id == 0x9001
    assert scenarios[4].payload_values == {"VertHeiRmdSts": 1}


def test_dry_run_validates_payloads_and_services(adc40_soc_dir):
    report = ProtocolSpikeRunner(adc40_soc_dir).run_dry()

    assert report.name == "someipy-protocol-spike-dry-run"
    assert report.failed is False
    assert [step.status for step in report.steps] == [SpikeStatus.PASS] * 5
    assert [step.name for step in report.steps] == [
        "udp-ff-method",
        "tcp-method",
        "udp-event",
        "tcp-event",
        "field-getter-notifier",
    ]
    assert [step.data["service_id"] for step in report.steps] == [
        "0x080D",
        "0x0F01",
        "0x080E",
        "0x080A",
        "0x080C",
    ]
    assert all(step.data["payload_hex"] for step in report.steps)

    assert report.steps[0].data == {
        "service_id": "0x080D",
        "payload_hex": "01",
        "transport": "UDP",
        "method_id": "0x0001",
        "rr_ff": "FF",
    }
    assert report.steps[1].data == {
        "service_id": "0x0F01",
        "payload_hex": "0000000000000001",
        "transport": "TCP",
        "method_id": "0x0001",
        "rr_ff": "FF",
    }
    assert report.steps[2].data == {
        "service_id": "0x080E",
        "payload_hex": "4148000042c68000",
        "transport": "UDP",
        "event_id": "0x8001",
        "send_strategy": "Cycle",
        "eventgroup_id": "0x0001",
    }
    assert report.steps[3].data == {
        "service_id": "0x080A",
        "payload_hex": "010203",
        "transport": "TCP",
        "event_id": "0x8001",
        "send_strategy": "Trigger",
        "eventgroup_id": "0x0001",
    }
    assert report.steps[4].data == {
        "service_id": "0x080C",
        "payload_hex": "01",
        "transport": "TCP",
        "getter_id": "0x1001",
        "notifier_id": "0x9001",
        "notifier_eventgroup_id": "0x0001",
        "getter_transport": "TCP",
        "notifier_transport": "TCP",
    }


def test_dry_run_fails_when_field_getter_is_missing(adc40_soc_dir):
    scenario = _field_scenario(adc40_soc_dir)
    assert scenario.field is not None
    scenario = replace(
        scenario,
        field=FieldDefinition(
            name=scenario.field.name,
            getter=None,
            setter=scenario.field.setter,
            notifier=scenario.field.notifier,
        ),
    )

    step = ProtocolSpikeRunner(adc40_soc_dir)._dry_step(scenario)

    assert step.status is SpikeStatus.FAIL
    assert "getter" in step.detail


def test_dry_run_fails_when_field_notifier_id_is_wrong(adc40_soc_dir):
    scenario = _field_scenario(adc40_soc_dir)
    assert scenario.field is not None
    assert scenario.field.notifier is not None
    scenario = replace(
        scenario,
        field=FieldDefinition(
            name=scenario.field.name,
            getter=scenario.field.getter,
            setter=scenario.field.setter,
            notifier=replace(scenario.field.notifier, element_id=0x9002),
        ),
    )

    step = ProtocolSpikeRunner(adc40_soc_dir)._dry_step(scenario)

    assert step.status is SpikeStatus.FAIL
    assert "notifier" in step.detail


def test_real_run_skips_when_someipy_api_missing(adc40_soc_dir):
    probe = _FakeProbe(SomeipyApiStatus(available=False, detail="fake API missing"))

    report = ProtocolSpikeRunner(adc40_soc_dir).run_real(api_probe=probe)

    assert report.name == "someipy-protocol-spike-real-run"
    assert report.failed is False
    assert len(report.steps) == 1
    assert report.steps[0].name == "someipy-api"
    assert report.steps[0].status is SpikeStatus.SKIP
    assert "fake API missing" in report.steps[0].detail
    assert probe.require_module_called is False


def test_real_run_records_api_available_before_network_attempt(adc40_soc_dir):
    probe = _FakeProbe(
        SomeipyApiStatus(available=True, detail="fake API available"),
        require_error=RuntimeError("fake network boundary"),
    )

    report = ProtocolSpikeRunner(adc40_soc_dir).run_real(api_probe=probe)

    assert report.name == "someipy-protocol-spike-real-run"
    assert report.failed is True
    assert [step.name for step in report.steps] == ["someipy-api", "real-loopback"]
    assert report.steps[0].status is SpikeStatus.PASS
    assert "fake API available" in report.steps[0].detail
    assert report.steps[1].status is SpikeStatus.FAIL
    assert "fake network boundary" in report.steps[1].detail


def test_real_run_starts_daemon_and_passes_matching_client_config(adc40_soc_dir, monkeypatch):
    api = _FakeSomeipyApi()
    probe = _FakeProbe(
        SomeipyApiStatus(available=True, detail="fake API available"),
        module=api,
    )
    daemon_process = _FakeSomeipydProcess()
    started = []

    def fake_start(config, work_dir):
        started.append((config, work_dir))
        return daemon_process

    monkeypatch.setattr("someip_gui_tool.spike.runner.SomeipydProcess.start", fake_start)

    report = ProtocolSpikeRunner(adc40_soc_dir).run_real(
        api_probe=probe,
        local_ip="127.0.0.42",
        base_port=32000,
        start_daemon=True,
    )

    assert report.failed is False
    assert [step.name for step in report.steps[:2]] == ["someipy-api", "someipyd"]
    assert report.steps[1].status is SpikeStatus.PASS
    assert len(started) == 1
    assert started[0][0].interface == "127.0.0.42"
    assert api.connect_kwargs == {
        "use_tcp": True,
        "tcp_host": "127.0.0.1",
        "tcp_port": 30500,
    }
    assert daemon_process.stopped is True


@pytest.mark.asyncio
async def test_real_async_runs_scenarios_and_event_paths(adc40_soc_dir, monkeypatch):
    def forbidden_private_protocol(self, transport):
        raise AssertionError("runner must use protocol_for")

    monkeypatch.setattr(SomeipyServiceFactory, "_protocol", forbidden_private_protocol)
    api = _FakeSomeipyApi()

    steps = await ProtocolSpikeRunner(adc40_soc_dir)._run_real_async(
        api=api,
        local_ip="127.0.0.1",
        base_port=31000,
    )

    assert [step.name for step in steps] == [
        "udp-ff-method",
        "tcp-method",
        "udp-event",
        "tcp-event",
        "field-getter-notifier",
    ]
    assert [step.status for step in steps] == [SpikeStatus.PASS] * 5
    assert [server.start_awaited for server in api.servers] == [True] * 5
    assert [server.stop_awaited for server in api.servers] == [True] * 5
    assert [server.endpoint_port for server in api.servers] == [
        31000,
        31010,
        31020,
        31030,
        31040,
    ]
    assert [client.endpoint_port for client in api.clients] == [
        31001,
        31011,
        31021,
        31031,
        31041,
    ]
    assert [client.is_available_awaited for client in api.clients] == [True] * 5
    assert api.daemon.disconnect_awaited is True

    subscriptions = [
        (client.service.service_id, eventgroup.id, eventgroup.events[0].id, eventgroup.events[0].protocol)
        for client in api.clients
        for eventgroup, _ttl in client.subscriptions
    ]
    assert subscriptions == [
        (0x080E, 0x0001, 0x8001, "UDP"),
        (0x080A, 0x0001, 0x8001, "TCP"),
        (0x080C, 0x0001, 0x9001, "TCP"),
    ]
    sent_events = [
        (server.service.service_id, eventgroup_id, event_id, payload.hex())
        for server in api.servers
        for eventgroup_id, event_id, payload in server.sent_events
    ]
    assert sent_events == [
        (0x080E, 0x0001, 0x8001, "4148000042c68000"),
        (0x080A, 0x0001, 0x8001, "010203"),
        (0x080C, 0x0001, 0x9001, "01"),
    ]
    field_step = steps[-1]
    assert field_step.data["getter_id"] == "0x1001"
    assert field_step.data["notifier_id"] == "0x9001"
    assert "notifier" in field_step.detail


@pytest.mark.asyncio
async def test_real_async_stops_offer_and_disconnects_when_start_fails(adc40_soc_dir):
    api = _FakeSomeipyApi(start_error=RuntimeError("start broke"))

    with pytest.raises(RuntimeError, match="start broke"):
        await ProtocolSpikeRunner(adc40_soc_dir)._run_real_async(
            api=api,
            local_ip="127.0.0.1",
            base_port=31000,
        )

    assert len(api.servers) == 1
    assert api.servers[0].stop_awaited is True
    assert api.daemon.disconnect_awaited is True


def _field_scenario(adc40_soc_dir) -> ProtocolScenario:
    return build_scenarios(adc40_soc_dir)[4]


class _FakeProbe:
    def __init__(
        self,
        status: SomeipyApiStatus,
        require_error: Exception | None = None,
        module=None,
    ):
        self._status = status
        self._require_error = require_error
        self._module = module
        self.require_module_called = False

    def probe(self):
        return self._status

    def require_module(self):
        self.require_module_called = True
        if self._require_error is not None:
            raise self._require_error
        return self._module if self._module is not None else _FakeSomeipyApi()


class _FakeSomeipydProcess:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeMethod:
    def __init__(self, id, protocol, method_handler=None):
        self.id = id
        self.protocol = protocol
        self.method_handler = method_handler


class _FakeEvent:
    def __init__(self, id, protocol):
        self.id = id
        self.protocol = protocol


class _FakeEventGroup:
    def __init__(self, id, events):
        self.id = id
        self.events = events


class _FakeBuilder:
    def __init__(self):
        self.service_id = None
        self.major_version = None
        self.minor_version = None
        self.methods = []
        self.eventgroups = []

    def with_service_id(self, id):
        self.service_id = id
        return self

    def with_major_version(self, major_version):
        self.major_version = major_version
        return self

    def with_minor_version(self, minor_version):
        self.minor_version = minor_version
        return self

    def with_method(self, method):
        self.methods.append(method)
        return self

    def with_eventgroup(self, eventgroup):
        self.eventgroups.append(eventgroup)
        return self

    def build(self):
        return SimpleNamespace(
            service_id=self.service_id,
            major_version=self.major_version,
            minor_version=self.minor_version,
            methods=self.methods,
            eventgroups=self.eventgroups,
        )


class _FakeServerServiceInstance:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.start_awaited = False
        self.stop_awaited = False
        self.sent_events = []
        self.api.servers.append(self)

    async def start_offer(self):
        self.start_awaited = True
        if self.api.start_error is not None:
            raise self.api.start_error

    async def stop_offer(self):
        self.stop_awaited = True

    def send_event(self, eventgroup_id, event_id, payload):
        self.sent_events.append((eventgroup_id, event_id, payload))


class _FakeClientServiceInstance:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.is_available_awaited = False
        self.subscriptions = []
        self.api.clients.append(self)

    async def is_available(self):
        self.is_available_awaited = True
        return True

    def subscribe_eventgroup(self, eventgroup, ttl_subscription_seconds=None):
        self.subscriptions.append((eventgroup, ttl_subscription_seconds))


class _FakeDaemon:
    def __init__(self):
        self.disconnect_awaited = False

    async def disconnect_from_daemon(self):
        self.disconnect_awaited = True


class _FakeSomeipyApi:
    Method = _FakeMethod
    Event = _FakeEvent
    EventGroup = _FakeEventGroup
    ServiceBuilder = _FakeBuilder
    TransportLayerProtocol = SimpleNamespace(TCP="TCP", UDP="UDP")

    def __init__(self, start_error=None):
        self.daemon = _FakeDaemon()
        self.servers = []
        self.clients = []
        self.connect_kwargs = None
        self.start_error = start_error
        self.ServerServiceInstance = self._server_service_instance
        self.ClientServiceInstance = self._client_service_instance

    async def connect_to_someipy_daemon(self, **kwargs):
        self.connect_kwargs = kwargs
        return self.daemon

    def _server_service_instance(self, **kwargs):
        return _FakeServerServiceInstance(api=self, **kwargs)

    def _client_service_instance(self, **kwargs):
        return _FakeClientServiceInstance(api=self, **kwargs)
