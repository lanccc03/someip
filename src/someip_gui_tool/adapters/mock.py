from __future__ import annotations

from dataclasses import dataclass

from someip_gui_tool.adapters.base import SomeIpAdapter
from someip_gui_tool.domain.models import EventDefinition, MethodDefinition, ServiceDefinition


@dataclass(frozen=True)
class AdapterCall:
    name: str
    details: dict[str, object]


class MockSomeIpAdapter(SomeIpAdapter):
    def __init__(self) -> None:
        self.calls: list[AdapterCall] = []

    async def start_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("start_service", {"service_id": service.service_id_hex}))

    async def stop_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("stop_service", {"service_id": service.service_id_hex}))

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> bytes | None:
        self.calls.append(
            AdapterCall(
                "call_method",
                {
                    "service_id": service.service_id_hex,
                    "method_id": method.method_id_hex,
                    "payload": payload.hex(),
                },
            )
        )
        return None

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "subscribe_eventgroup",
                {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
            )
        )

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        self.calls.append(
            AdapterCall(
                "publish_event",
                {
                    "service_id": service.service_id_hex,
                    "event_id": event.event_id_hex,
                    "payload": payload.hex(),
                },
            )
        )

    async def shutdown(self) -> None:
        self.calls.append(AdapterCall("shutdown", {}))
