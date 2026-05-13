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


class ServiceRegistry:
    def __init__(self, services: list[ServiceDefinition]) -> None:
        self.services = services
        self._by_id = {service.service_id: service for service in services}

    @classmethod
    def load_directory(cls, directory: Path) -> ServiceRegistry:
        return cls(load_service_directory(directory))

    def get_service(self, service_id: int) -> ServiceDefinition:
        return self._by_id[service_id]

    def find_element(self, service_id: int, element_id: int) -> ElementDefinition:
        service = self.get_service(service_id)

        for method in service.methods:
            if method.method_id == element_id:
                return method

        for event in service.events:
            if event.event_id == element_id:
                return event

        for field in service.fields:
            for part in (field.getter, field.setter, field.notifier):
                if part is not None and part.element_id == element_id:
                    return part

        raise KeyError((service_id, element_id))
