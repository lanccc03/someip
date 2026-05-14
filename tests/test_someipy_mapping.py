from dataclasses import dataclass
from types import SimpleNamespace

from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.parsing.service_json import load_service_definition


@dataclass(frozen=True)
class FakeMethod:
    id: int
    protocol: str
    method_handler: object | None = None


@dataclass(frozen=True)
class FakeEvent:
    id: int
    protocol: str


@dataclass(frozen=True)
class FakeEventGroup:
    id: int
    events: list[FakeEvent]


class FakeBuilder:
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


class FakeProtocol:
    TCP = "TCP"
    UDP = "UDP"


def fake_api():
    return SimpleNamespace(
        ServiceBuilder=FakeBuilder,
        Method=FakeMethod,
        Event=FakeEvent,
        EventGroup=FakeEventGroup,
        TransportLayerProtocol=FakeProtocol,
    )


def test_builds_udp_method_and_event_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    mapped = SomeipyServiceFactory(fake_api()).build_service(service)

    assert mapped.service_id == 0x080D
    assert mapped.major_version == 1
    assert mapped.minor_version == 0
    assert [method.id for method in mapped.methods] == [0x0001]
    assert mapped.methods[0].protocol == "UDP"
    assert [group.id for group in mapped.eventgroups] == [0x0001]
    assert [event.id for event in mapped.eventgroups[0].events] == [0x8001]
    assert mapped.eventgroups[0].events[0].protocol == "UDP"


def test_builds_field_notifier_as_eventgroup(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    mapped = SomeipyServiceFactory(fake_api()).build_service(service)

    assert [method.id for method in mapped.methods] == [0x1001]
    assert [group.id for group in mapped.eventgroups] == [0x0001]
    assert [event.id for event in mapped.eventgroups[0].events] == [0x9001]
