from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from someip_gui_tool.adapters.base import (
    AdapterMethodResult,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


FIELD_GET_NOT_IMPLEMENTED = (
    "someipy field getter execution is not implemented in Phase A adapter skeleton"
)
FIELD_SET_NOT_IMPLEMENTED = (
    "someipy field setter execution is not implemented in Phase A adapter skeleton"
)
_PORT_STRIDE = 10
_CYCLIC_OFFER_DELAY_MS = 1000
_CLIENT_ID_BASE = 0x1000


@dataclass
class _SomeipyServiceRuntime:
    mapped_service: Any
    server: Any
    client: Any
    endpoint_port: int
    client_port: int
    active_eventgroups: set[int]


class SomeipyAdapter(SomeIpAdapter):
    def __init__(
        self,
        *,
        api: Any | None = None,
        local_ip: str,
        base_port: int,
    ) -> None:
        self._api = api
        self._local_ip = local_ip
        self._base_port = base_port
        self._daemon: Any | None = None
        self._daemon_lock = asyncio.Lock()
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}
        self._service_runtimes: dict[int, _SomeipyServiceRuntime] = {}
        self._service_order: dict[int, int] = {}

    async def start_service(self, service: ServiceDefinition) -> None:
        runtime = await self._runtime_for_service(service)
        await _maybe_await(runtime.server.start_offer())

    async def stop_service(self, service: ServiceDefinition) -> None:
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            await _maybe_await(runtime.server.stop_offer())
        self._service_runtimes.pop(service.service_id, None)
        self._service_order.pop(service.service_id, None)
        self._clear_service_handlers(service.service_id)

    async def offer_service(self, service: ServiceDefinition) -> None:
        await self.start_service(service)

    async def find_service(self, service: ServiceDefinition) -> bool:
        await self._ensure_daemon()
        return False

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if method.rr_ff == "FF":
            return AdapterMethodResult(status="limited", detail=SOMEIPY_FF_LIMITATION)
        return AdapterMethodResult(
            status="error",
            detail=(
                "RR method execution is not enabled until a matching RR fixture "
                "or adapter request/response path is available."
            ),
        )

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
        await self._ensure_daemon()
        raise NotImplementedError(
            "someipy subscribe_eventgroup execution is not implemented in Phase A adapter skeleton"
        )

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        await self._ensure_daemon()
        raise NotImplementedError(
            "someipy unsubscribe_eventgroup execution is not implemented in Phase A adapter skeleton"
        )

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        await self._ensure_daemon()
        raise NotImplementedError(
            "someipy publish_event execution is not implemented in Phase A adapter skeleton"
        )

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no getter")
        await self._ensure_daemon()
        return AdapterMethodResult(status="error", detail=FIELD_GET_NOT_IMPLEMENTED)

    async def field_set(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.setter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no setter")
        await self._ensure_daemon()
        return AdapterMethodResult(status="error", detail=FIELD_SET_NOT_IMPLEMENTED)

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        await self._ensure_daemon()
        raise NotImplementedError(
            "someipy field_notify execution is not implemented in Phase A adapter skeleton"
        )

    async def shutdown(self) -> None:
        async with self._daemon_lock:
            daemon = self._daemon
            self._daemon = None
            self._event_handlers.clear()
            if daemon is None:
                return
            disconnect = getattr(daemon, "disconnect_from_daemon", None)
            if disconnect is not None:
                result = disconnect()
                if inspect.isawaitable(result):
                    await result

    async def _ensure_daemon(self) -> Any:
        if self._daemon is not None:
            return self._daemon

        async with self._daemon_lock:
            if self._daemon is not None:
                return self._daemon

            api = self._api
            if api is None:
                api = SomeipyApiProbe().require_module()
                self._api = api

            config = SomeipydConfig(
                interface=self._local_ip,
                tcp_host=self._local_ip,
                tcp_port=self._base_port,
            ).client_config()
            self._daemon = await api.connect_to_someipy_daemon(config)
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
        pass  # implemented in Task 4

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

    async def _runtime_for_service(self, service: ServiceDefinition) -> _SomeipyServiceRuntime:
        runtime = self._service_runtimes.get(service.service_id)
        if runtime is not None:
            return runtime

        daemon = await self._ensure_daemon()
        api = self._api
        if api is None:
            raise RuntimeError("someipy API was not initialized")

        factory = SomeipyServiceFactory(
            api,
            method_handler_factory=self._method_handler_factory(api),
        )
        mapped_service = factory.build_service(service)
        service_index = self._service_order.setdefault(service.service_id, len(self._service_order))
        endpoint_port = self._base_port + service_index * _PORT_STRIDE
        client_port = endpoint_port + 1
        server = api.ServerServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=self._local_ip,
            endpoint_port=endpoint_port,
            ttl=int(service.deployment.offer_ttl_s),
            cyclic_offer_delay_ms=_CYCLIC_OFFER_DELAY_MS,
        )
        client = api.ClientServiceInstance(
            daemon=daemon,
            service=mapped_service,
            instance_id=service.deployment.instance_id,
            endpoint_ip=self._local_ip,
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
        )
        self._service_runtimes[service.service_id] = runtime
        return runtime


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
