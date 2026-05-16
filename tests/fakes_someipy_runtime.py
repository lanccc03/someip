from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable


@dataclass(frozen=True)
class FakeMethod:
    id: int
    protocol: str
    method_handler: Callable[[bytes, tuple[str, int]], object] | None = None


@dataclass(frozen=True)
class FakeEvent:
    id: int
    protocol: str


@dataclass(frozen=True)
class FakeEventGroup:
    id: int
    events: list[FakeEvent]

    @property
    def has_udp(self) -> bool:
        return any(event.protocol == "UDP" for event in self.events)

    @property
    def has_tcp(self) -> bool:
        return any(event.protocol == "TCP" for event in self.events)

    def to_json(self) -> str:
        return f"eventgroup:{self.id}"


class FakeService:
    def __init__(
        self,
        *,
        id: int,
        major_version: int,
        minor_version: int,
        methods: list[FakeMethod],
        eventgroups: list[FakeEventGroup],
    ) -> None:
        self.id = id
        self.major_version = major_version
        self.minor_version = minor_version
        self.methods = {method.id: method for method in methods}
        self.eventgroups = {group.id: group for group in eventgroups}
        self.eventgroupids = set(self.eventgroups)


class FakeServiceBuilder:
    def __init__(self) -> None:
        self.service_id: int | None = None
        self.major_version: int | None = None
        self.minor_version: int | None = None
        self.methods: list[FakeMethod] = []
        self.eventgroups: list[FakeEventGroup] = []

    def with_service_id(self, id: int) -> FakeServiceBuilder:
        self.service_id = id
        return self

    def with_major_version(self, major_version: int) -> FakeServiceBuilder:
        self.major_version = major_version
        return self

    def with_minor_version(self, minor_version: int) -> FakeServiceBuilder:
        self.minor_version = minor_version
        return self

    def with_method(self, method: FakeMethod) -> FakeServiceBuilder:
        self.methods.append(method)
        return self

    def with_eventgroup(self, eventgroup: FakeEventGroup) -> FakeServiceBuilder:
        self.eventgroups.append(eventgroup)
        return self

    def build(self) -> FakeService:
        if self.service_id is None:
            raise ValueError("service id was not configured")
        if self.major_version is None:
            raise ValueError("major version was not configured")
        if self.minor_version is None:
            raise ValueError("minor version was not configured")
        return FakeService(
            id=self.service_id,
            major_version=self.major_version,
            minor_version=self.minor_version,
            methods=self.methods,
            eventgroups=self.eventgroups,
        )


class FakeDaemon:
    def __init__(self, api: FakeSomeipyApi) -> None:
        self.api = api
        self.disconnected = False

    async def disconnect_from_daemon(self) -> None:
        self.disconnected = True


class FakeServerServiceInstance:
    def __init__(
        self,
        *,
        daemon: FakeDaemon,
        service: FakeService,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        ttl: int = 0,
        cyclic_offer_delay_ms: int = 2000,
    ) -> None:
        self.daemon = daemon
        self.service = service
        self.instance_id = instance_id
        self.endpoint_ip = endpoint_ip
        self.endpoint_port = endpoint_port
        self.ttl = ttl
        self.cyclic_offer_delay_ms = cyclic_offer_delay_ms
        self.start_awaited = False
        self.stop_awaited = False
        self.sent_events: list[tuple[int, int, bytes]] = []
        daemon.api.servers.append(self)

    async def start_offer(self) -> None:
        self.start_awaited = True

    async def stop_offer(self) -> None:
        self.stop_awaited = True

    def send_event(self, eventgroup_id: int, event_id: int, payload: bytes) -> None:
        self.sent_events.append((eventgroup_id, event_id, payload))
        for client in self.daemon.api.clients:
            if client.service.id == self.service.id:
                client.deliver_event(eventgroup_id, event_id, payload)


class FakeClientServiceInstance:
    def __init__(
        self,
        *,
        daemon: FakeDaemon,
        service: FakeService,
        instance_id: int,
        endpoint_ip: str,
        endpoint_port: int,
        client_id: int = 0,
    ) -> None:
        self.daemon = daemon
        self.service = service
        self.instance_id = instance_id
        self.endpoint_ip = endpoint_ip
        self.endpoint_port = endpoint_port
        self.client_id = client_id
        self.callback: Callable[[int, bytes], None] | None = None
        self.subscribed_eventgroups: list[tuple[int, int]] = []
        self.unsubscribed_eventgroups: list[int] = []
        daemon.api.clients.append(self)

    def register_callback(self, callback: Callable[[int, bytes], None]) -> None:
        self.callback = callback

    async def is_available(self) -> bool:
        sequence = self.daemon.api.availability_sequences.get(self.service.id, [True])
        index = self.daemon.api.availability_calls.get(self.service.id, 0)
        self.daemon.api.availability_calls[self.service.id] = index + 1
        if index < len(sequence):
            return sequence[index]
        return sequence[-1]

    def subscribe_eventgroup(
        self,
        eventgroup: FakeEventGroup,
        ttl_subscription_seconds: int,
    ) -> None:
        self.subscribed_eventgroups.append((eventgroup.id, ttl_subscription_seconds))

    def unsubscribe_eventgroup(self, eventgroup: FakeEventGroup) -> None:
        self.unsubscribed_eventgroups.append(eventgroup.id)

    async def call_method(self, method_id: int, payload: bytes) -> object:
        server = self.daemon.api.server_for_service(self.service.id)
        method = server.service.methods[method_id]
        if method.method_handler is None:
            return self.daemon.api.method_result(payload=b"")
        result = method.method_handler(payload, (self.endpoint_ip, self.endpoint_port))
        if asyncio.iscoroutine(result):
            result = await result
        return result

    def deliver_event(self, eventgroup_id: int, event_id: int, payload: bytes) -> None:
        subscribed_ids = {group_id for group_id, ttl in self.subscribed_eventgroups}
        if eventgroup_id in subscribed_ids and self.callback is not None:
            self.callback(event_id, payload)


class FakeSomeipyApi:
    class TransportLayerProtocol:
        TCP = "TCP"
        UDP = "UDP"

    class MessageType:
        RESPONSE = "RESPONSE"
        ERROR = "ERROR"

    class ReturnCode:
        E_OK = "E_OK"
        E_NOT_OK = "E_NOT_OK"

    ServiceBuilder = FakeServiceBuilder
    Method = FakeMethod
    Event = FakeEvent
    EventGroup = FakeEventGroup

    def __init__(
        self,
        *,
        availability_sequences: dict[int, list[bool]] | None = None,
        connect_sleep: float | None = None,
    ) -> None:
        self.connect_sleep = connect_sleep
        self.connect_started_count = 0
        self.connect_configs: list[dict[str, object]] = []
        self.availability_sequences = availability_sequences or {}
        self.availability_calls: dict[int, int] = {}
        self.servers: list[FakeServerServiceInstance] = []
        self.clients: list[FakeClientServiceInstance] = []
        self.daemon = FakeDaemon(self)

    async def connect_to_someipy_daemon(self, config: dict[str, object]) -> FakeDaemon:
        self.connect_started_count += 1
        if self.connect_sleep is not None:
            await asyncio.sleep(self.connect_sleep)
        self.connect_configs.append(config)
        return self.daemon

    def ServerServiceInstance(self, **kwargs: object) -> FakeServerServiceInstance:
        return FakeServerServiceInstance(**kwargs)

    def ClientServiceInstance(self, **kwargs: object) -> FakeClientServiceInstance:
        return FakeClientServiceInstance(**kwargs)

    def MethodResult(self) -> object:
        return self.method_result(payload=b"")

    def method_result(self, payload: bytes) -> object:
        return SimpleNamespace(
            message_type=self.MessageType.RESPONSE,
            return_code=self.ReturnCode.E_OK,
            payload=payload,
        )

    def server_for_service(self, service_id: int) -> FakeServerServiceInstance:
        for server in self.servers:
            if server.service.id == service_id:
                return server
        raise KeyError(f"server for service 0x{service_id:04X} was not started")
