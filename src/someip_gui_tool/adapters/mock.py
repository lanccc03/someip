from __future__ import annotations

from dataclasses import dataclass

from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


@dataclass(frozen=True)
class AdapterCall:
    name: str
    details: dict[str, object]


class MockSomeIpAdapter(SomeIpAdapter):
    def __init__(self) -> None:
        self.calls: list[AdapterCall] = []
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}

    async def start_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("start_service", {"service_id": service.service_id_hex}))

    async def stop_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("stop_service", {"service_id": service.service_id_hex}))

    async def offer_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("offer_service", {"service_id": service.service_id_hex}))

    async def find_service(self, service: ServiceDefinition) -> bool:
        self.calls.append(AdapterCall("find_service", {"service_id": service.service_id_hex}))
        return True

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
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
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        return AdapterMethodResult(
            status="success",
            detail="mock method call completed",
            payload=payload,
        )

    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        self.calls.append(
            AdapterCall(
                "register_event_handler",
                {"service_id": service.service_id_hex, "event_id": event.event_id_hex},
            )
        )
        self._event_handlers.setdefault((service.service_id, event.event_id), []).append(handler)

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "subscribe_eventgroup",
                {"service_id": service.service_id_hex, "eventgroup_id": f"0x{eventgroup_id:04X}"},
            )
        )

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        self.calls.append(
            AdapterCall(
                "unsubscribe_eventgroup",
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
        adapter_event = AdapterEvent(
            service_id=service.service_id,
            element_id=event.event_id,
            eventgroup_id=event.eventgroup_id,
            payload=payload,
        )
        for handler in self._event_handlers.get((service.service_id, event.event_id), []):
            handler(adapter_event)

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        self.calls.append(
            AdapterCall(
                "field_get",
                {"service_id": service.service_id_hex, "field": field.name, "payload": payload.hex()},
            )
        )
        if field.getter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no getter")
        return AdapterMethodResult(
            status="success",
            detail="mock field getter completed",
            payload=payload,
        )

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        self.calls.append(
            AdapterCall(
                "field_notify",
                {"service_id": service.service_id_hex, "field": field.name, "payload": payload.hex()},
            )
        )

    async def shutdown(self) -> None:
        self.calls.append(AdapterCall("shutdown", {}))
