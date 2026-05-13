from __future__ import annotations

from abc import ABC, abstractmethod

from someip_gui_tool.domain.models import EventDefinition, MethodDefinition, ServiceDefinition


class SomeIpAdapter(ABC):
    @abstractmethod
    async def start_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError
