from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from someip_gui_tool.adapters.base import AdapterEvent, AdapterMethodResult, SomeIpAdapter
from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.core.runtime_config import RuntimeServiceConfig
from someip_gui_tool.domain.enums import Role, TraceDirection, TransportProtocol
from someip_gui_tool.domain.models import (
    EventDefinition,
    FieldDefinition,
    FieldPartDefinition,
    MethodDefinition,
    ServiceDefinition,
)
from someip_gui_tool.tracing.trace_model import MessageTraceEntry, RunLogEntry


class RuntimeSession:
    def __init__(self, adapter: SomeIpAdapter, codec: PayloadCodec | None = None) -> None:
        self.adapter = adapter
        self.codec = codec or PayloadCodec()
        self.run_log: list[RunLogEntry] = []
        self.trace: list[MessageTraceEntry] = []

    async def start_service(
        self,
        service: ServiceDefinition,
        config: RuntimeServiceConfig,
    ) -> None:
        await self.adapter.start_service(service)
        self._log(
            "info",
            "Core",
            f"Started service {service.service_name} ({service.service_id_hex})",
            service_id=service.service_id_hex,
        )

    async def stop_service(self, service: ServiceDefinition) -> None:
        await self.adapter.stop_service(service)
        self._log(
            "info",
            "Core",
            f"Stopped service {service.service_name} ({service.service_id_hex})",
            service_id=service.service_id_hex,
        )

    async def call_method(
        self,
        service: ServiceDefinition,
        method: MethodDefinition,
        values: dict[str, Any],
    ) -> AdapterMethodResult:
        payload = self.codec.encode_parameters(method.parameters, values)
        result = await self.adapter.call_method(service, method, payload)
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.TX,
            element_type="Method",
            element_name=method.name,
            element_id=method.method_id_hex,
            eventgroup_id=None,
            transport=method.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=method.rr_ff,
            result=result.status,
            error_message=_error_detail(result),
        )
        self._log(
            "info",
            "Core",
            f"Called method {method.name} result={result.status}",
            service_id=service.service_id_hex,
            element_id=method.method_id_hex,
            error_detail=_error_detail(result),
        )
        return result

    async def subscribe_event(self, service: ServiceDefinition, event: EventDefinition) -> None:
        if event.eventgroup_id is None:
            raise ValueError(f"Event {event.name!r} has no eventgroup id")
        await self.adapter.subscribe_eventgroup(service, event.eventgroup_id)
        self._log(
            "info",
            "Core",
            f"Subscribed eventgroup 0x{event.eventgroup_id:04X} for {event.name}",
            service_id=service.service_id_hex,
            element_id=event.event_id_hex,
        )

    async def publish_event(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        values: dict[str, Any],
    ) -> None:
        payload = self.codec.encode_parameters(event.parameters, values)
        await self.adapter.publish_event(service, event, payload)
        self._trace(
            service=service,
            role=Role.SERVER,
            direction=TraceDirection.TX,
            element_type="Event",
            element_name=event.name,
            element_id=event.event_id_hex,
            eventgroup_id=_eventgroup_hex(event.eventgroup_id),
            transport=event.transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            rr_ff=None,
            result="success",
            error_message=None,
        )
        self._log(
            "info",
            "Core",
            f"Published event {event.name} payload={payload.hex()}",
            service_id=service.service_id_hex,
            element_id=event.event_id_hex,
        )

    async def field_get(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        values: dict[str, Any],
    ) -> AdapterMethodResult:
        if field.getter is None:
            raise ValueError(f"Field {field.name!r} has no getter")
        payload = self.codec.encode_parameters(field.getter.parameters, values)
        result = await self.adapter.field_get(service, field, payload)
        self._trace_field_part(
            service=service,
            field=field,
            part=field.getter,
            role=Role.CLIENT,
            direction=TraceDirection.TX,
            element_type="FieldGetter",
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            result=result.status,
            error_message=_error_detail(result),
        )
        self._log(
            "info",
            "Core",
            f"Field getter {field.name} result={result.status}",
            service_id=service.service_id_hex,
            element_id=_field_part_id_hex(field.getter),
            error_detail=_error_detail(result),
        )
        return result

    async def field_set(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        values: dict[str, Any],
    ) -> AdapterMethodResult:
        payload = (
            self.codec.encode_parameters(field.setter.parameters, values)
            if field.setter is not None
            else b""
        )
        result = await self.adapter.field_set(service, field, payload)
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.TX,
            element_type="FieldSetter",
            element_name=field.name,
            element_id=_field_part_id_hex(field.setter),
            eventgroup_id=_eventgroup_hex(field.setter.eventgroup_id) if field.setter else None,
            transport=_field_part_transport(field.setter, service),
            raw_payload_hex=payload.hex(),
            decoded_payload=values if field.setter is not None else {},
            rr_ff=None,
            result=result.status,
            error_message=_error_detail(result),
        )
        self._log(
            "info",
            "Core",
            f"Field setter {field.name} result={result.status}",
            service_id=service.service_id_hex,
            element_id=_field_part_id_hex(field.setter),
            error_detail=_error_detail(result),
        )
        return result

    async def field_notify(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        values: dict[str, Any],
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        payload = self.codec.encode_parameters(field.notifier.parameters, values)
        await self.adapter.field_notify(service, field, payload)
        self._trace_field_part(
            service=service,
            field=field,
            part=field.notifier,
            role=Role.SERVER,
            direction=TraceDirection.TX,
            element_type="FieldNotifier",
            raw_payload_hex=payload.hex(),
            decoded_payload=values,
            result="success",
            error_message=None,
        )
        self._log(
            "info",
            "Core",
            f"Field notifier {field.name} payload={payload.hex()}",
            service_id=service.service_id_hex,
            element_id=_field_part_id_hex(field.notifier),
        )

    async def register_event_trace(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
    ) -> None:
        await self.adapter.register_event_handler(
            service,
            event,
            lambda adapter_event: self._append_event_rx_trace(service, event, adapter_event),
        )

    async def register_field_notifier_trace(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        await self.adapter.register_field_notifier_handler(
            service,
            field,
            lambda adapter_event: self._append_field_notifier_rx_trace(
                service,
                field,
                adapter_event,
            ),
        )

    def _append_event_rx_trace(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        adapter_event: AdapterEvent,
    ) -> None:
        decoded_payload, payload_decode_status, error_message = self._decode_payload(
            event.parameters,
            adapter_event.payload,
        )
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.RX,
            element_type="Event",
            element_name=event.name,
            element_id=f"0x{adapter_event.element_id:04X}",
            eventgroup_id=_eventgroup_hex(adapter_event.eventgroup_id),
            transport=event.transport,
            raw_payload_hex=adapter_event.payload.hex(),
            decoded_payload=decoded_payload,
            rr_ff=None,
            result="success" if payload_decode_status == "ok" else "error",
            error_message=error_message,
            payload_decode_status=payload_decode_status,
        )

    def _append_field_notifier_rx_trace(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
        adapter_event: AdapterEvent,
    ) -> None:
        if field.notifier is None:
            return
        decoded_payload, payload_decode_status, error_message = self._decode_payload(
            field.notifier.parameters,
            adapter_event.payload,
        )
        self._trace(
            service=service,
            role=Role.CLIENT,
            direction=TraceDirection.RX,
            element_type="FieldNotifier",
            element_name=field.name,
            element_id=f"0x{adapter_event.element_id:04X}",
            eventgroup_id=_eventgroup_hex(adapter_event.eventgroup_id),
            transport=field.notifier.transport,
            raw_payload_hex=adapter_event.payload.hex(),
            decoded_payload=decoded_payload,
            rr_ff=None,
            result="success" if payload_decode_status == "ok" else "error",
            error_message=error_message,
            payload_decode_status=payload_decode_status,
        )

    def _decode_payload(
        self,
        parameters: list[Any],
        payload: bytes,
    ) -> tuple[dict[str, Any], str, str | None]:
        try:
            return self.codec.decode_parameters(parameters, payload), "ok", None
        except ValueError as exc:
            return {}, "error", str(exc)

    def _trace_field_part(
        self,
        *,
        service: ServiceDefinition,
        field: FieldDefinition,
        part: FieldPartDefinition,
        role: Role,
        direction: TraceDirection,
        element_type: str,
        raw_payload_hex: str,
        decoded_payload: dict[str, Any],
        result: str,
        error_message: str | None,
    ) -> None:
        self._trace(
            service=service,
            role=role,
            direction=direction,
            element_type=element_type,
            element_name=field.name,
            element_id=_field_part_id_hex(part),
            eventgroup_id=_eventgroup_hex(part.eventgroup_id),
            transport=part.transport,
            raw_payload_hex=raw_payload_hex,
            decoded_payload=decoded_payload,
            rr_ff=None,
            result=result,
            error_message=error_message,
        )

    def _log(
        self,
        level: str,
        source: str,
        message: str,
        *,
        service_id: str | None = None,
        element_id: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        self.run_log.append(
            RunLogEntry(
                timestamp=datetime.now(timezone.utc),
                level=level,
                source=source,
                message=message,
                service_id=service_id,
                element_id=element_id,
                error_detail=error_detail,
            )
        )

    def _trace(
        self,
        *,
        service: ServiceDefinition,
        role: Role,
        direction: TraceDirection,
        element_type: str,
        element_name: str,
        element_id: str,
        eventgroup_id: str | None,
        transport: TransportProtocol,
        raw_payload_hex: str,
        decoded_payload: dict[str, Any],
        rr_ff: str | None,
        result: str,
        error_message: str | None,
        payload_decode_status: str = "ok",
    ) -> None:
        self.trace.append(
            MessageTraceEntry(
                timestamp=datetime.now(timezone.utc),
                direction=direction,
                role=role,
                service_name=service.service_name,
                service_id=service.service_id_hex,
                instance_id=f"0x{service.deployment.instance_id:04X}",
                element_type=element_type,
                element_name=element_name,
                element_id=element_id,
                eventgroup_id=eventgroup_id,
                transport=transport,
                local_endpoint="",
                remote_endpoint="",
                rr_ff=rr_ff,
                raw_payload_hex=raw_payload_hex,
                decoded_payload=decoded_payload,
                payload_decode_status=payload_decode_status,
                result=result,
                error_message=error_message,
            )
        )


def _eventgroup_hex(eventgroup_id: int | None) -> str | None:
    if eventgroup_id is None:
        return None
    return f"0x{eventgroup_id:04X}"


def _field_part_id_hex(part: FieldPartDefinition | None) -> str:
    if part is None:
        return "0x0000"
    return f"0x{part.element_id:04X}"


def _field_part_transport(
    part: FieldPartDefinition | None,
    service: ServiceDefinition,
) -> TransportProtocol:
    if part is None:
        return service.deployment.default_transport
    return part.transport


def _error_detail(result: AdapterMethodResult) -> str | None:
    if result.status == "success":
        return None
    return result.detail
