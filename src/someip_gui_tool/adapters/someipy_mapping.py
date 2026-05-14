from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from someip_gui_tool.domain.enums import TransportProtocol
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ServiceDefinition,
)


MethodHandlerFactory = Callable[
    [ServiceDefinition, MethodDefinition | FieldPartDefinition],
    object,
]

SOMEIPY_SUPPORTS_FIRE_AND_FORGET = False
FIRE_AND_FORGET_LIMITATION = (
    "someipy does not currently implement fire-and-forget methods; "
    'RR/FF == "FF" cannot be proven by service mapping alone.'
)


class SomeipyServiceFactory:
    def __init__(
        self,
        someipy_api: Any,
        method_handler_factory: MethodHandlerFactory | None = None,
    ) -> None:
        self._api = someipy_api
        self._method_handler_factory = method_handler_factory

    def build_service(self, service: ServiceDefinition) -> Any:
        builder = (
            self._api.ServiceBuilder()
            .with_service_id(service.service_id)
            .with_major_version(service.deployment.major_version)
            .with_minor_version(service.deployment.minor_version)
        )

        for method in self._method_parts(service):
            builder = builder.with_method(
                self._api.Method(
                    id=(
                        method.method_id
                        if isinstance(method, MethodDefinition)
                        else method.element_id
                    ),
                    protocol=self.protocol_for(method.transport),
                    method_handler=(
                        self._method_handler_factory(service, method)
                        if self._method_handler_factory is not None
                        else None
                    ),
                )
            )

        for eventgroup_id, events in self._eventgroups(service).items():
            builder = builder.with_eventgroup(
                self._api.EventGroup(
                    id=eventgroup_id,
                    events=[
                        self._api.Event(
                            id=event_id,
                            protocol=self.protocol_for(transport),
                        )
                        for event_id, transport in events
                    ],
                )
            )

        return builder.build()

    def protocol_for(self, transport: TransportProtocol) -> Any:
        if transport == TransportProtocol.TCP:
            return self._api.TransportLayerProtocol.TCP
        if transport == TransportProtocol.UDP:
            return self._api.TransportLayerProtocol.UDP
        raise ValueError(f"Unsupported transport: {transport!r}")

    def _protocol(self, transport: TransportProtocol) -> Any:
        return self.protocol_for(transport)

    def _method_parts(
        self, service: ServiceDefinition
    ) -> list[MethodDefinition | FieldPartDefinition]:
        parts: list[MethodDefinition | FieldPartDefinition] = list(service.methods)
        for field in service.fields:
            if field.getter is not None:
                parts.append(field.getter)
            if field.setter is not None:
                parts.append(field.setter)
        return parts

    def _eventgroups(
        self, service: ServiceDefinition
    ) -> dict[int, list[tuple[int, TransportProtocol]]]:
        groups: dict[int, list[tuple[int, TransportProtocol]]] = defaultdict(list)
        seen: set[tuple[int, int]] = set()
        for event in service.events:
            self._add_event(groups, seen, event)
        for field in service.fields:
            if field.notifier is not None:
                self._add_field_notifier(groups, seen, field.notifier)
        return dict(groups)

    def _add_event(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        seen: set[tuple[int, int]],
        event: EventDefinition,
    ) -> None:
        if event.eventgroup_id is None:
            return
        self._raise_for_duplicate_event(seen, event.eventgroup_id, event.event_id)
        groups[event.eventgroup_id].append((event.event_id, event.transport))

    def _add_field_notifier(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        seen: set[tuple[int, int]],
        notifier: FieldPartDefinition,
    ) -> None:
        if notifier.eventgroup_id is None:
            return
        self._raise_for_duplicate_event(seen, notifier.eventgroup_id, notifier.element_id)
        groups[notifier.eventgroup_id].append((notifier.element_id, notifier.transport))

    def _raise_for_duplicate_event(
        self,
        seen: set[tuple[int, int]],
        eventgroup_id: int,
        event_id: int,
    ) -> None:
        key = (eventgroup_id, event_id)
        if key in seen:
            raise ValueError(
                f"Duplicate event id 0x{event_id:04X} in eventgroup 0x{eventgroup_id:04X}"
            )
        seen.add(key)
