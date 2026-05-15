from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


@dataclass(frozen=True)
class AdapterMethodResult:
    status: str
    detail: str
    payload: bytes | None = None


@dataclass(frozen=True)
class AdapterEvent:
    service_id: int
    element_id: int
    eventgroup_id: int | None
    payload: bytes


EventHandler = Callable[[AdapterEvent], None]


class SomeIpAdapter(ABC):
    @abstractmethod
    async def start_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def offer_service(self, service: ServiceDefinition) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_service(self, service: ServiceDefinition) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        raise NotImplementedError

    @abstractmethod
    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
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
    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        raise NotImplementedError

    @abstractmethod
    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self) -> None:
        raise NotImplementedError
