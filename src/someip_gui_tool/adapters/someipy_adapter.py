from __future__ import annotations

import inspect
from typing import Any

from someip_gui_tool.adapters.base import (
    AdapterMethodResult,
    EventHandler,
    SomeIpAdapter,
)
from someip_gui_tool.adapters.capabilities import SOMEIPY_FF_LIMITATION
from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    MethodDefinition,
    ServiceDefinition,
)


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
        self._event_handlers: dict[tuple[int, int], list[EventHandler]] = {}

    async def start_service(self, service: ServiceDefinition) -> None:
        await self._ensure_daemon()

    async def stop_service(self, service: ServiceDefinition) -> None:
        return None

    async def offer_service(self, service: ServiceDefinition) -> None:
        await self._ensure_daemon()

    async def find_service(self, service: ServiceDefinition) -> bool:
        await self._ensure_daemon()
        return True

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

    async def unsubscribe_eventgroup(self, service: ServiceDefinition, eventgroup_id: int) -> None:
        await self._ensure_daemon()

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        payload: bytes,
    ) -> None:
        await self._ensure_daemon()

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.getter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no getter")
        await self._ensure_daemon()
        return AdapterMethodResult(
            status="success",
            detail="someipy field getter Phase A skeleton completed",
            payload=payload,
        )

    async def field_set(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> AdapterMethodResult:
        if field.setter is None:
            return AdapterMethodResult(status="error", detail=f"Field {field.name!r} has no setter")
        await self._ensure_daemon()
        return AdapterMethodResult(
            status="success",
            detail="someipy field setter Phase A skeleton completed",
            payload=payload,
        )

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        payload: bytes,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        await self._ensure_daemon()

    async def shutdown(self) -> None:
        if self._daemon is None:
            return
        disconnect = getattr(self._daemon, "disconnect_from_daemon", None)
        if disconnect is not None:
            result = disconnect()
            if inspect.isawaitable(result):
                await result
        self._daemon = None

    async def _ensure_daemon(self) -> Any:
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
