from __future__ import annotations

from collections import defaultdict
from typing import Any

from someip_gui_tool.domain.enums import TransportProtocol
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ServiceDefinition,
)


class SomeipyServiceFactory:
    def __init__(self, someipy_api: Any) -> None:
        self._api = someipy_api

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
                    protocol=self._protocol(method.transport),
                    method_handler=None,
                )
            )

        for eventgroup_id, events in self._eventgroups(service).items():
            builder = builder.with_eventgroup(
                self._api.EventGroup(
                    id=eventgroup_id,
                    events=[
                        self._api.Event(id=event_id, protocol=self._protocol(transport))
                        for event_id, transport in events
                    ],
                )
            )

        return builder.build()

    def _protocol(self, transport: TransportProtocol) -> Any:
        if transport == TransportProtocol.TCP:
            return self._api.TransportLayerProtocol.TCP
        if transport == TransportProtocol.UDP:
            return self._api.TransportLayerProtocol.UDP
        raise ValueError(f"Unsupported transport: {transport!r}")

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
        for event in service.events:
            self._add_event(groups, event)
        for field in service.fields:
            if field.notifier is not None:
                self._add_field_notifier(groups, field.notifier)
        return dict(groups)

    def _add_event(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        event: EventDefinition,
    ) -> None:
        if event.eventgroup_id is None:
            return
        groups[event.eventgroup_id].append((event.event_id, event.transport))

    def _add_field_notifier(
        self,
        groups: dict[int, list[tuple[int, TransportProtocol]]],
        notifier: FieldPartDefinition,
    ) -> None:
        if notifier.eventgroup_id is None:
            return
        groups[notifier.eventgroup_id].append((notifier.element_id, notifier.transport))
