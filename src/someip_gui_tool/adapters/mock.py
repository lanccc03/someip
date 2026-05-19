from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterServiceAvailability,
    AdapterStartConfig,
    AdapterSubscriptionResult,
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
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


class MockSomeIpAdapter(SomeIpAdapter):
    def __init__(self) -> None:
        self.calls: list[AdapterCall] = []
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}
        self._subscribed_eventgroups: set[tuple[int, int]] = set()

    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
        details: dict[str, object] = {"service_id": service.service_id_hex}
        if config is not None:
            details.update(
                {
                    "role": config.role.value,
                    "local_ip": config.local_ip,
                    "server_port": config.server_port,
                    "client_port": config.client_port,
                }
            )
        self.calls.append(AdapterCall("start_service", details))

    async def stop_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("stop_service", {"service_id": service.service_id_hex}))

    async def offer_service(self, service: ServiceDefinition) -> None:
        self.calls.append(AdapterCall("offer_service", {"service_id": service.service_id_hex}))

    async def find_service(self, service: ServiceDefinition) -> bool:
        self.calls.append(AdapterCall("find_service", {"service_id": service.service_id_hex}))
        return True

    async def check_service_available(self, service: ServiceDefinition) -> AdapterServiceAvailability:
        self.calls.append(AdapterCall("check_service_available", {"service_id": service.service_id_hex}))
        return AdapterServiceAvailability(available=True, detail="mock service is available")

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

    async def register_field_notifier_handler(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        handler: EventHandler,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        self.calls.append(
            AdapterCall(
                "register_field_notifier_handler",
                {"service_id": service.service_id_hex, "field": field.name},
            )
        )
        key = (service.service_id, field.notifier.element_id)
        self._event_handlers.setdefault(key, []).append(handler)

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
        if not self._is_subscribed(service.service_id, event.eventgroup_id):
            return
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

    async def field_set(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        self.calls.append(
            AdapterCall(
                "field_set",
                {"service_id": service.service_id_hex, "field": field.name, "payload": payload.hex()},
            )
        )
        if field.setter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no setter")
        return AdapterMethodResult(
            status="success",
            detail="mock field setter completed",
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
        if not self._is_subscribed(service.service_id, field.notifier.eventgroup_id):
            return
        adapter_event = AdapterEvent(
            service_id=service.service_id,
            element_id=field.notifier.element_id,
            eventgroup_id=field.notifier.eventgroup_id,
            payload=payload,
        )
        key = (service.service_id, field.notifier.element_id)
        for handler in self._event_handlers.get(key, []):
            handler(adapter_event)

    async def shutdown(self) -> None:
        self.calls.append(AdapterCall("shutdown", {}))
        self._event_handlers.clear()
        self._subscribed_eventgroups.clear()

    def _is_subscribed(self, service_id: int, eventgroup_id: int | None) -> bool:
        if eventgroup_id is None:
            return False
        return (service_id, eventgroup_id) in self._subscribed_eventgroups
