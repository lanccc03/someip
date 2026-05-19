from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from someip_gui_tool.domain.enums import Role
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


@dataclass(frozen=True)
class AdapterStartConfig:
    role: Role
    local_ip: str
    server_port: int
    client_port: int
    multicast_ip: str
    offer_ttl_s: float
    find_ttl_s: float


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


@dataclass(frozen=True)
class AdapterServiceAvailability:
    available: bool
    detail: str


@dataclass(frozen=True)
class AdapterSubscriptionResult:
    status: str
    detail: str
    service_available: bool | None = None


SUBSCRIPTION_REQUESTED = "requested"
SUBSCRIPTION_PENDING = "pending"
SUBSCRIPTION_CANCEL_REQUESTED = "cancel-requested"
SUBSCRIPTION_NOT_REQUESTED = "not-requested"


EventHandler = Callable[[AdapterEvent], None]


class SomeIpAdapter(ABC):
    @abstractmethod
    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
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
    async def check_service_available(self, service: ServiceDefinition) -> AdapterServiceAvailability:
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
    async def register_field_notifier_handler(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        handler: EventHandler,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def subscribe_eventgroup(
        self,
        service: ServiceDefinition,
        eventgroup_id: int,
    ) -> AdapterSubscriptionResult:
        raise NotImplementedError

    @abstractmethod
    async def unsubscribe_eventgroup(
        self,
        service: ServiceDefinition,
        eventgroup_id: int,
    ) -> AdapterSubscriptionResult:
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
    async def field_set(
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
