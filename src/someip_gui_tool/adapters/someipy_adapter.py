from __future__ import annotations

import asyncio
import inspect
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterStartConfig,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


_PORT_STRIDE = 10
_CYCLIC_OFFER_DELAY_MS = 1000
_CLIENT_ID_BASE = 0x1000
FIND_AVAILABILITY_ATTEMPTS = 3
FIND_AVAILABILITY_DELAY_S = 0.05
SD_PORT = 30490


def _endpoint_host(ip_address: str) -> str:
    return ip_address.split("/", 1)[0]


@dataclass
class _SomeipyServiceRuntime:
    mapped_service: Any
    server: Any
    client: Any
    endpoint_port: int
    client_port: int
    active_eventgroups: set[int]
    start_config: AdapterStartConfig | None
    offer_ttl_s: float
    find_ttl_s: float


class SomeipyAdapter(SomeIpAdapter):
    def __init__(
        self,
        *,
        api: Any | None = None,
        local_ip: str,
        base_port: int,
        start_daemon: bool = False,
        daemon_work_dir: Path | None = None,
        sd_socket_factory: Any | None = None,
    ) -> None:
        self._api = api
        self._local_ip = local_ip
        self._base_port = base_port
        self._start_daemon = start_daemon
        self._daemon_work_dir = daemon_work_dir
        self._sd_socket_factory = sd_socket_factory
        self._sd_session_id = 0
        self._owned_daemon_process: SomeipydProcess | None = None
        self._owned_temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._daemon: Any | None = None
        self._daemon_lock = asyncio.Lock()
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}
        self._service_runtimes: dict[int, _SomeipyServiceRuntime] = {}
        self._next_service_index = 0

    async def start_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> None:
        runtime = await self._runtime_for_service(service, config)
        if config is None:
            await _maybe_await(runtime.server.start_offer())

    async def stop_service(self, service: ServiceDefinition) -> None:
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            await _maybe_await(runtime.server.stop_offer())
        self._service_runtimes.pop(service.service_id, None)
        self._clear_service_handlers(service.service_id)

    async def offer_service(self, service: ServiceDefinition) -> None:
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.start_offer())

    async def find_service(self, service: ServiceDefinition) -> bool:
        runtime = await self._runtime_for_service(service)
        self._send_find_service_request(service, runtime)
        for attempt in range(FIND_AVAILABILITY_ATTEMPTS):
            if bool(await _maybe_await(runtime.client.is_available())):
                return True
            if attempt < FIND_AVAILABILITY_ATTEMPTS - 1:
                await asyncio.sleep(FIND_AVAILABILITY_DELAY_S)
        return False

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        runtime = await self._runtime_for_service(service)
        result = await _maybe_await(runtime.client.call_method(method.method_id, payload))
        return self._adapter_method_result(result, "someipy method call completed")

    async def register_event_handler(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        handler: EventHandler,
    ) -> None:
        self._event_handlers.setdefault((service.service_id, event.event_id), []).append(handler)

    async def register_field_notifier_handler(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        handler: EventHandler,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        key = (service.service_id, field.notifier.element_id)
        self._event_handlers.setdefault(key, []).append(handler)

    async def subscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        runtime = await self._runtime_for_service(service)
        eventgroup = self._eventgroup_for(service, eventgroup_id)
        await _maybe_await(
            runtime.client.subscribe_eventgroup(
                eventgroup,
                ttl_subscription_seconds=int(runtime.find_ttl_s),
            )
        )
        runtime.active_eventgroups.add(eventgroup_id)

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        runtime = await self._runtime_for_service(service)
        eventgroup = self._eventgroup_for(service, eventgroup_id)
        await _maybe_await(runtime.client.unsubscribe_eventgroup(eventgroup))
        runtime.active_eventgroups.discard(eventgroup_id)

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        if event.eventgroup_id is None:
            raise ValueError(f"Event {event.name!r} has no eventgroup id")
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.send_event(event.eventgroup_id, event.event_id, payload))

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no getter")
        runtime = await self._runtime_for_service(service)
        result = await _maybe_await(runtime.client.call_method(field.getter.element_id, payload))
        return self._adapter_method_result(result, "someipy field getter completed")

    async def field_set(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.setter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no setter")
        await self._ensure_daemon()
        return AdapterMethodResult(status="error", detail="someipy field setter execution is not implemented")

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        if field.notifier.eventgroup_id is None:
            raise ValueError(f"Field {field.name!r} notifier has no eventgroup id")
        runtime = await self._runtime_for_service(service)
        await _maybe_await(
            runtime.server.send_event(
                field.notifier.eventgroup_id,
                field.notifier.element_id,
                payload,
            )
        )

    def _send_find_service_request(
        self,
        service: ServiceDefinition,
        runtime: _SomeipyServiceRuntime,
    ) -> None:
        from someipy._internal._sd.deserialization.sd_serialization import (
            serialize_sd_message,
        )
        from someipy._internal._sd.entries.find_service_entry import FindServiceEntry
        from someipy._internal._sd.sd_message import SdMessage

        config = runtime.start_config
        local_ip = _endpoint_host(config.local_ip) if config is not None else self._local_ip
        multicast_ip = config.multicast_ip if config is not None else "239.192.255.251"

        self._sd_session_id = (self._sd_session_id % 0xFFFF) + 1
        sd_message = SdMessage()
        sd_message.session_id = self._sd_session_id
        sd_message.reboot_flag = False
        sd_message.entries.append(
            FindServiceEntry(
                service_id=service.service_id,
                instance_id=service.deployment.instance_id,
                major_version=service.deployment.major_version,
                minor_version=service.deployment.minor_version,
            )
        )
        payload = serialize_sd_message(sd_message)

        socket_factory = self._sd_socket_factory
        if socket_factory is None:
            socket_factory = lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with socket_factory() as sd_socket:
            sd_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            sd_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
            sd_socket.bind((local_ip, 0))
            sd_socket.sendto(payload, (multicast_ip, SD_PORT))

    def _adapter_method_result(self, result: Any, success_detail: str) -> AdapterMethodResult:
        payload = getattr(result, "payload", None)
        return_code = getattr(result, "return_code", None)
        return_code_name = getattr(return_code, "name", None) or str(return_code)
        if return_code_name not in {"E_OK", "ReturnCode.E_OK"}:
            return AdapterMethodResult(
                status="error",
                detail=f"someipy method returned {return_code_name}",
                payload=payload if isinstance(payload, bytes) else None,
            )
        if payload is not None and not isinstance(payload, bytes):
            return AdapterMethodResult(
                status="error",
                detail=f"someipy method payload must be bytes, got {type(payload).__name__}",
            )
        return AdapterMethodResult(status="success", detail=success_detail, payload=payload)

    def _stop_owned_daemon_process(self) -> None:
        if self._owned_daemon_process is not None:
            self._owned_daemon_process.stop()
            self._owned_daemon_process = None
        if self._owned_temp_dir is not None:
            self._owned_temp_dir.cleanup()
            self._owned_temp_dir = None

    async def shutdown(self) -> None:
        async with self._daemon_lock:
            daemon = self._daemon
            self._daemon = None
            for runtime in list(self._service_runtimes.values()):
                try:
                    await _maybe_await(runtime.server.stop_offer())
                except Exception:
                    pass
            self._service_runtimes.clear()
            self._event_handlers.clear()
            try:
                if daemon is not None:
                    disconnect = getattr(daemon, "disconnect_from_daemon", None)
                    if disconnect is not None:
                        result = disconnect()
                        if inspect.isawaitable(result):
                            await result
            finally:
                self._stop_owned_daemon_process()

    async def _ensure_daemon(self, config: AdapterStartConfig | None = None) -> Any:
        if self._daemon is not None:
            return self._daemon

        async with self._daemon_lock:
            if self._daemon is not None:
                return self._daemon

            api = self._api
            if api is None:
                api = SomeipyApiProbe().require_module()
                self._api = api

            daemon_ip = self._local_ip if config is None else _endpoint_host(config.local_ip)
            sd_address = (
                "239.192.255.251"
                if config is None
                else config.multicast_ip
            )

            if self._start_daemon and self._owned_daemon_process is None:
                work_dir = self._daemon_work_dir
                if work_dir is None:
                    self._owned_temp_dir = tempfile.TemporaryDirectory(prefix="someipyd-adapter-")
                    work_dir = Path(self._owned_temp_dir.name)
                daemon_config = SomeipydConfig(
                    interface=daemon_ip,
                    sd_address=sd_address,
                    tcp_host=daemon_ip,
                    tcp_port=self._base_port,
                )
                self._owned_daemon_process = SomeipydProcess.start(
                    config=daemon_config,
                    work_dir=work_dir,
                )

            daemon_config = SomeipydConfig(
                interface=daemon_ip,
                sd_address=sd_address,
                tcp_host=daemon_ip,
                tcp_port=self._base_port,
            ).client_config()
            try:
                self._daemon = await api.connect_to_someipy_daemon(daemon_config)
            except Exception:
                self._stop_owned_daemon_process()
                raise
            return self._daemon

    def _clear_service_handlers(self, service_id: int) -> None:
        stale_keys = [key for key in self._event_handlers if key[0] == service_id]
        for key in stale_keys:
            del self._event_handlers[key]

    def _dispatch_event(
        self,
        service: ServiceDefinition,
        event_id: int,
        payload: bytes,
    ) -> None:
        eventgroup_id = self._eventgroup_id_for_element(service, event_id)
        adapter_event = AdapterEvent(
            service_id=service.service_id,
            element_id=event_id,
            eventgroup_id=eventgroup_id,
            payload=payload,
        )
        for handler in list(self._event_handlers.get((service.service_id, event_id), [])):
            handler(adapter_event)

    def _eventgroup_id_for_element(
        self,
        service: ServiceDefinition,
        element_id: int,
    ) -> int | None:
        for event in service.events:
            if event.event_id == element_id:
                return event.eventgroup_id
        for field in service.fields:
            notifier = field.notifier
            if notifier is not None and notifier.element_id == element_id:
                return notifier.eventgroup_id
        return None

    def _method_handler_factory(self, api: Any) -> Any:
        def handler_factory(service: ServiceDefinition, method_part: Any) -> Any:
            async def method_handler(input_data: bytes, addr: tuple[str, int]) -> Any:
                result_type = getattr(api, "MethodResult", None)
                result = result_type() if result_type is not None else SimpleNamespace()
                message_type = getattr(api, "MessageType", None)
                return_code = getattr(api, "ReturnCode", None)
                result.message_type = (
                    getattr(message_type, "RESPONSE", None)
                    if message_type is not None
                    else "RESPONSE"
                )
                result.return_code = (
                    getattr(return_code, "E_OK", None) if return_code is not None else "E_OK"
                )
                result.payload = input_data
                return result

            return method_handler

        return handler_factory

    async def _runtime_for_service(
        self,
        service: ServiceDefinition,
        config: AdapterStartConfig | None = None,
    ) -> _SomeipyServiceRuntime:
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            if config is None or runtime.start_config == config:
                return runtime
            await _maybe_await(runtime.server.stop_offer())
            self._service_runtimes.pop(service.service_id, None)

        daemon = await self._ensure_daemon(config)
        api = self._api
        if api is None:
            raise RuntimeError("someipy API was not initialized")

        factory = SomeipyServiceFactory(
            api,
            method_handler_factory=self._method_handler_factory(api),
        )
        mapped_service = factory.build_service(service)
        service_index = self._next_service_index
        self._next_service_index += 1
        if config is None:
            endpoint_ip = self._local_ip
            endpoint_port = self._base_port + service_index * _PORT_STRIDE
            client_port = endpoint_port + 1
            offer_ttl_s = service.deployment.offer_ttl_s
            find_ttl_s = service.deployment.find_ttl_s
        else:
            endpoint_ip = _endpoint_host(config.local_ip)
            endpoint_port = config.server_port
            client_port = config.client_port
            offer_ttl_s = config.offer_ttl_s
            find_ttl_s = config.find_ttl_s
        server = api.ServerServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=endpoint_ip,
            endpoint_port=endpoint_port,
            ttl=int(offer_ttl_s),
            cyclic_offer_delay_ms=_CYCLIC_OFFER_DELAY_MS,
        )
        client = api.ClientServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=endpoint_ip,
            endpoint_port=client_port,
            client_id=_CLIENT_ID_BASE + service_index,
        )
        client.register_callback(
            lambda event_id, payload: self._dispatch_event(service, event_id, payload)
        )
        runtime = _SomeipyServiceRuntime(
            mapped_service=mapped_service,
            server=server,
            client=client,
            endpoint_port=endpoint_port,
            client_port=client_port,
            active_eventgroups=set(),
            start_config=config,
            offer_ttl_s=offer_ttl_s,
            find_ttl_s=find_ttl_s,
        )
        self._service_runtimes[service.service_id] = runtime
        return runtime

    def _eventgroup_for(self, service: ServiceDefinition, eventgroup_id: int) -> Any:
        api = self._api
        if api is None:
            raise RuntimeError("someipy API was not initialized")
        factory = SomeipyServiceFactory(api)
        events = []
        for event in service.events:
            if event.eventgroup_id == eventgroup_id:
                events.append(
                    api.Event(
                        id=event.event_id,
                        protocol=factory.protocol_for(event.transport),
                    )
                )
        for field in service.fields:
            notifier = field.notifier
            if notifier is not None and notifier.eventgroup_id == eventgroup_id:
                events.append(
                    api.Event(
                        id=notifier.element_id,
                        protocol=factory.protocol_for(notifier.transport),
                    )
                )
        if not events:
            raise ValueError(
                f"Eventgroup 0x{eventgroup_id:04X} not found in service {service.service_id_hex}"
            )
        return api.EventGroup(id=eventgroup_id, events=events)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
