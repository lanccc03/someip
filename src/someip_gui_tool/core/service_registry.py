from __future__ import annotations

from pathlib import Path

from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ServiceDefinition,
)
from someip_gui_tool.parsing.service_json import load_service_directory

ElementDefinition = MethodDefinition | EventDefinition | FieldPartDefinition


def _hex(value: int) -> str:
    return f"0x{value:04X}"


class ServiceRegistry:
    def __init__(self, services: list[ServiceDefinition]) -> None:
        self.services = services
        self._by_id: dict[int, ServiceDefinition] = {}
        for service in services:
            if service.service_id in self._by_id:
                raise ValueError(f"Duplicate service id {_hex(service.service_id)}")
            self._by_id[service.service_id] = service

    @classmethod
    def load_directory(cls, directory: Path) -> ServiceRegistry:
        return cls(load_service_directory(directory))

    def get_service(self, service_id: int) -> ServiceDefinition:
        return self._by_id[service_id]

    def find_element(self, service_id: int, element_id: int) -> ElementDefinition:
        service = self.get_service(service_id)
        matches: list[ElementDefinition] = []

        for method in service.methods:
            if method.method_id == element_id:
                matches.append(method)

        for event in service.events:
            if event.event_id == element_id:
                matches.append(event)

        for field in service.fields:
            for part in (field.getter, field.setter, field.notifier):
                if part is not None and part.element_id == element_id:
                    matches.append(part)

        if len(matches) > 1:
            raise ValueError(
                f"Duplicate element id {_hex(element_id)} in service {_hex(service_id)}"
            )

        if matches:
            return matches[0]

        raise KeyError(
            f"Element {_hex(element_id)} not found in service {_hex(service_id)}"
        )
