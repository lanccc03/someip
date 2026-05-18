from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from someip_gui_tool.adapters.base import (
    AdapterEvent,
    AdapterMethodResult,
    AdapterStartConfig,
    SomeIpAdapter,
)
from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.core.runtime_config import (
    RuntimeProblem,
    RuntimeServiceConfig,
    validate_runtime_config,
)
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
        self.problems: list[RuntimeProblem] = []
        self.run_log: list[RunLogEntry] = []
        self.trace: list[MessageTraceEntry] = []
        self._configs: dict[int, RuntimeServiceConfig] = {}
        self._active_service_ids: set[int] = set()
        self._registered_trace_keys: set[tuple[str, int, int]] = set()
        self._trace_generations: dict[int, int] = {}

    async def start_service(
        self,
        service: ServiceDefinition,
        config: RuntimeServiceConfig,
    ) -> None:
        problems = validate_runtime_config(service, config)
        self.problems.extend(problems)
        for problem in problems:
            self._log(
                problem.severity,
                "Core",
                problem.message,
                service_id=service.service_id_hex,
                error_detail=problem.code,
            )
        errors = [problem for problem in problems if problem.severity == "error"]
        if errors:
            problem_codes = ", ".join(problem.code for problem in errors)
            raise ValueError(f"Runtime config invalid: {problem_codes}")
        adapter_config = _adapter_start_config(service, config)
        try:
            await self.adapter.start_service(service, adapter_config)
            if config.role is Role.SERVER:
                await self.adapter.offer_service(service)
                self._log(
                    "info",
                    "Core",
                    f"Offered service {service.service_name} ({service.service_id_hex})",
                    service_id=service.service_id_hex,
                )
            else:
                found = await self.adapter.find_service(service)
                if found:
                    self._log(
                        "info",
                        "Core",
                        f"Found service {service.service_name} ({service.service_id_hex})",
                        service_id=service.service_id_hex,
                    )
                else:
                    message = (
                        f"Service {service.service_name} ({service.service_id_hex}) "
                        "is not available after find-service polling."
                    )
                    self.problems.append(
                        RuntimeProblem(
                            code="find_service_unavailable",
                            severity="warning",
                            message=message,
                            service_id=service.service_id,
                        )
                    )
                    self._log(
                        "warning",
                        "Core",
                        message,
                        service_id=service.service_id_hex,
                        error_detail="find_service_unavailable",
                    )
        except Exception as exc:
            self._record_adapter_exception(
                "start_service_adapter_exception",
                service,
                f"Adapter failed to start service {service.service_name}",
                exc,
            )
            raise
        self._configs[service.service_id] = config
        self._active_service_ids.add(service.service_id)
        self._log(
            "info",
            "Core",
            f"Started service {service.service_name} ({service.service_id_hex})",
            service_id=service.service_id_hex,
        )

    async def stop_service(self, service: ServiceDefinition) -> None:
        try:
            await self.adapter.stop_service(service)
        except Exception as exc:
            self._record_adapter_exception(
                "stop_service_adapter_exception",
                service,
                f"Adapter failed to stop service {service.service_name}",
                exc,
            )
            raise
        self._active_service_ids.discard(service.service_id)
        self._configs.pop(service.service_id, None)
        self._registered_trace_keys = {
            key for key in self._registered_trace_keys if key[1] != service.service_id
        }
        self._trace_generations[service.service_id] = self._trace_generation(service) + 1
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
        try:
            payload = self.codec.encode_parameters(method.parameters, values)
        except (KeyError, TypeError, ValueError) as exc:
            return self._record_encode_error_result(
                service=service,
                role=Role.CLIENT,
                direction=TraceDirection.TX,
                element_type="Method",
                element_name=method.name,
                element_id=method.method_id_hex,
                eventgroup_id=None,
                transport=method.transport,
                rr_ff=method.rr_ff,
                error=exc,
            )
        try:
            result = await self.adapter.call_method(service, method, payload)
        except Exception as exc:
            self._record_adapter_exception(
                "call_method_adapter_exception",
                service,
                f"Adapter failed to call method {method.name}",
                exc,
                element_id=method.method_id_hex,
            )
            raise
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
        if result.payload is not None:
            self._trace_response_payload(
                service=service,
                role=Role.CLIENT,
                element_type="Method",
                element_name=method.name,
                element_id=method.method_id_hex,
                eventgroup_id=None,
                transport=method.transport,
                parameters=method.parameters,
                payload=result.payload,
                result_status=result.status,
                rr_ff=method.rr_ff,
            )
        log_level = "error" if result.status == "error" else "info"
        if result.status == "error":
            self._record_adapter_result_problem(
                "call_method_adapter_error",
                service,
                f"Adapter returned error for method {method.name}: {result.detail}",
            )
        self._log(
            log_level,
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
        try:
            await self.adapter.subscribe_eventgroup(service, event.eventgroup_id)
        except Exception as exc:
            self._record_adapter_exception(
                "subscribe_event_adapter_exception",
                service,
                f"Adapter failed to subscribe event {event.name}",
                exc,
                element_id=event.event_id_hex,
            )
            raise
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
        try:
            payload = self.codec.encode_parameters(event.parameters, values)
        except (KeyError, TypeError, ValueError) as exc:
            self._record_encode_error_trace(
                service=service,
                role=Role.SERVER,
                direction=TraceDirection.TX,
                element_type="Event",
                element_name=event.name,
                element_id=event.event_id_hex,
                eventgroup_id=_eventgroup_hex(event.eventgroup_id),
                transport=event.transport,
                rr_ff=None,
                error=exc,
            )
            raise
        try:
            await self.adapter.publish_event(service, event, payload)
        except Exception as exc:
            self._record_adapter_exception(
                "publish_event_adapter_exception",
                service,
                f"Adapter failed to publish event {event.name}",
                exc,
                element_id=event.event_id_hex,
            )
            raise
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
        try:
            payload = self.codec.encode_parameters(field.getter.parameters, values)
        except (KeyError, TypeError, ValueError) as exc:
            return self._record_encode_error_result(
                service=service,
                role=Role.CLIENT,
                direction=TraceDirection.TX,
                element_type="FieldGetter",
                element_name=field.name,
                element_id=_field_part_id_hex(field.getter),
                eventgroup_id=_eventgroup_hex(field.getter.eventgroup_id),
                transport=field.getter.transport,
                rr_ff=None,
                error=exc,
            )
        try:
            result = await self.adapter.field_get(service, field, payload)
        except Exception as exc:
            self._record_adapter_exception(
                "field_get_adapter_exception",
                service,
                f"Adapter failed to get field {field.name}",
                exc,
                element_id=_field_part_id_hex(field.getter),
            )
            raise
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
        if result.payload is not None:
            self._trace_response_payload(
                service=service,
                role=Role.CLIENT,
                element_type="FieldGetter",
                element_name=field.name,
                element_id=_field_part_id_hex(field.getter),
                eventgroup_id=_eventgroup_hex(field.getter.eventgroup_id),
                transport=field.getter.transport,
                parameters=field.getter.parameters,
                payload=result.payload,
                result_status=result.status,
                rr_ff=None,
            )
        log_level = "error" if result.status == "error" else "info"
        if result.status == "error":
            self._record_adapter_result_problem(
                "field_get_adapter_error",
                service,
                f"Adapter returned error for field getter {field.name}: {result.detail}",
            )
        self._log(
            log_level,
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
        if field.setter is None:
            detail = f"Field {field.name!r} has no setter"
            self._trace(
                service=service,
                role=Role.CLIENT,
                direction=TraceDirection.TX,
                element_type="FieldSetter",
                element_name=field.name,
                element_id="missing",
                eventgroup_id=None,
                transport=service.deployment.default_transport,
                raw_payload_hex="",
                decoded_payload={},
                rr_ff=None,
                result="error",
                error_message=detail,
            )
            self._log(
                "error",
                "Core",
                f"Field setter {field.name} result=error",
                service_id=service.service_id_hex,
                element_id="missing",
                error_detail=detail,
            )
            return AdapterMethodResult(status="error", detail=detail)
        try:
            payload = self.codec.encode_parameters(field.setter.parameters, values)
        except (KeyError, TypeError, ValueError) as exc:
            return self._record_encode_error_result(
                service=service,
                role=Role.CLIENT,
                direction=TraceDirection.TX,
                element_type="FieldSetter",
                element_name=field.name,
                element_id=_field_part_id_hex(field.setter),
                eventgroup_id=_eventgroup_hex(field.setter.eventgroup_id),
                transport=field.setter.transport,
                rr_ff=None,
                error=exc,
            )
        try:
            result = await self.adapter.field_set(service, field, payload)
        except Exception as exc:
            self._record_adapter_exception(
                "field_set_adapter_exception",
                service,
                f"Adapter failed to set field {field.name}",
                exc,
                element_id=_field_part_id_hex(field.setter),
            )
            raise
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
        log_level = "error" if result.status == "error" else "info"
        if result.status == "error":
            self._record_adapter_result_problem(
                "field_set_adapter_error",
                service,
                f"Adapter returned error for field setter {field.name}: {result.detail}",
            )
        self._log(
            log_level,
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
        try:
            payload = self.codec.encode_parameters(field.notifier.parameters, values)
        except (KeyError, TypeError, ValueError) as exc:
            self._record_encode_error_trace(
                service=service,
                role=Role.SERVER,
                direction=TraceDirection.TX,
                element_type="FieldNotifier",
                element_name=field.name,
                element_id=_field_part_id_hex(field.notifier),
                eventgroup_id=_eventgroup_hex(field.notifier.eventgroup_id),
                transport=field.notifier.transport,
                rr_ff=None,
                error=exc,
            )
            raise
        try:
            await self.adapter.field_notify(service, field, payload)
        except Exception as exc:
            self._record_adapter_exception(
                "field_notify_adapter_exception",
                service,
                f"Adapter failed to notify field {field.name}",
                exc,
                element_id=_field_part_id_hex(field.notifier),
            )
            raise
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
        key = ("event", service.service_id, event.event_id)
        if key in self._registered_trace_keys:
            return
        generation = self._trace_generation(service)
        try:
            await self.adapter.register_event_handler(
                service,
                event,
                lambda adapter_event: self._append_event_rx_trace(
                    service,
                    event,
                    adapter_event,
                    generation,
                ),
            )
        except Exception as exc:
            self._record_adapter_exception(
                "register_event_trace_adapter_exception",
                service,
                f"Adapter failed to register event trace for {event.name}",
                exc,
                element_id=event.event_id_hex,
            )
            raise
        self._registered_trace_keys.add(key)

    async def register_field_notifier_trace(
        self,
        service: ServiceDefinition,
        field: FieldDefinition,
    ) -> None:
        if field.notifier is None:
            raise ValueError(f"Field {field.name!r} has no notifier")
        key = ("field-notifier", service.service_id, field.notifier.element_id)
        if key in self._registered_trace_keys:
            return
        generation = self._trace_generation(service)
        try:
            await self.adapter.register_field_notifier_handler(
                service,
                field,
                lambda adapter_event: self._append_field_notifier_rx_trace(
                    service,
                    field,
                    adapter_event,
                    generation,
                ),
            )
        except Exception as exc:
            self._record_adapter_exception(
                "register_field_notifier_trace_adapter_exception",
                service,
                f"Adapter failed to register field notifier trace for {field.name}",
                exc,
                element_id=_field_part_id_hex(field.notifier),
            )
            raise
        self._registered_trace_keys.add(key)

    def _append_event_rx_trace(
        self,
        service: ServiceDefinition,
        event: EventDefinition,
        adapter_event: AdapterEvent,
        generation: int,
    ) -> None:
        if not self._is_trace_callback_active(service, adapter_event, generation):
            return
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
        generation: int,
    ) -> None:
        if field.notifier is None or not self._is_trace_callback_active(
            service,
            adapter_event,
            generation,
        ):
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
        except (KeyError, TypeError, ValueError) as exc:
            return {}, "error", str(exc)

    def _trace_response_payload(
        self,
        *,
        service: ServiceDefinition,
        role: Role,
        element_type: str,
        element_name: str,
        element_id: str,
        eventgroup_id: str | None,
        transport: TransportProtocol,
        parameters: list[Any],
        payload: bytes,
        result_status: str,
        rr_ff: str | None,
    ) -> None:
        decoded_payload, payload_decode_status, error_message = self._decode_payload(
            parameters,
            payload,
        )
        self._trace(
            service=service,
            role=role,
            direction=TraceDirection.RX,
            element_type=element_type,
            element_name=element_name,
            element_id=element_id,
            eventgroup_id=eventgroup_id,
            transport=transport,
            raw_payload_hex=payload.hex(),
            decoded_payload=decoded_payload,
            rr_ff=rr_ff,
            result=result_status if payload_decode_status == "ok" else "error",
            error_message=error_message,
            payload_decode_status=payload_decode_status,
        )

    def _record_encode_error_result(
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
        rr_ff: str | None,
        error: Exception,
    ) -> AdapterMethodResult:
        detail = str(error)
        self._record_encode_error_trace(
            service=service,
            role=role,
            direction=direction,
            element_type=element_type,
            element_name=element_name,
            element_id=element_id,
            eventgroup_id=eventgroup_id,
            transport=transport,
            rr_ff=rr_ff,
            error=error,
        )
        return AdapterMethodResult(status="error", detail=detail)

    def _record_encode_error_trace(
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
        rr_ff: str | None,
        error: Exception,
    ) -> None:
        detail = str(error)
        self._trace(
            service=service,
            role=role,
            direction=direction,
            element_type=element_type,
            element_name=element_name,
            element_id=element_id,
            eventgroup_id=eventgroup_id,
            transport=transport,
            raw_payload_hex="",
            decoded_payload={},
            rr_ff=rr_ff,
            result="error",
            error_message=detail,
            payload_decode_status="encode-error",
        )
        self._log(
            "error",
            "Core",
            f"{element_type} {element_name} encode failed",
            service_id=service.service_id_hex,
            element_id=element_id,
            error_detail=detail,
        )

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

    def _record_adapter_exception(
        self,
        code: str,
        service: ServiceDefinition,
        message: str,
        error: Exception,
        *,
        element_id: str | None = None,
    ) -> None:
        detail = str(error)
        self.problems.append(
            RuntimeProblem(
                code=code,
                severity="error",
                message=f"{message}: {detail}",
                service_id=service.service_id,
            )
        )
        self._log(
            "error",
            "Adapter",
            message,
            service_id=service.service_id_hex,
            element_id=element_id,
            error_detail=detail,
        )

    def _record_adapter_result_problem(
        self,
        code: str,
        service: ServiceDefinition,
        message: str,
    ) -> None:
        self.problems.append(
            RuntimeProblem(
                code=code,
                severity="error",
                message=message,
                service_id=service.service_id,
            )
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
        local_endpoint, remote_endpoint = self._trace_endpoints(service)
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
                local_endpoint=local_endpoint,
                remote_endpoint=remote_endpoint,
                rr_ff=rr_ff,
                raw_payload_hex=raw_payload_hex,
                decoded_payload=decoded_payload,
                payload_decode_status=payload_decode_status,
                result=result,
                error_message=error_message,
            )
        )

    def _trace_endpoints(self, service: ServiceDefinition) -> tuple[str, str]:
        config = self._configs.get(service.service_id)
        if config is None:
            return "", ""
        role = Role(config.role)
        if role is Role.SERVER:
            local_port = config.server_port
            remote_port = config.client_port
        else:
            local_port = config.client_port
            remote_port = config.server_port
        return _format_endpoint(config.local_ip, local_port), _format_endpoint(
            config.remote_ip,
            remote_port,
        )

    def _is_trace_callback_active(
        self,
        service: ServiceDefinition,
        adapter_event: AdapterEvent,
        generation: int,
    ) -> bool:
        return (
            service.service_id in self._active_service_ids
            and adapter_event.service_id == service.service_id
            and generation == self._trace_generation(service)
        )

    def _trace_generation(self, service: ServiceDefinition) -> int:
        return self._trace_generations.get(service.service_id, 0)


def _adapter_start_config(
    service: ServiceDefinition,
    config: RuntimeServiceConfig,
) -> AdapterStartConfig:
    if config.server_port is None or config.client_port is None:
        raise ValueError("Runtime config must have server_port and client_port after validation.")
    return AdapterStartConfig(
        role=config.role,
        local_ip=config.local_ip,
        server_port=config.server_port,
        client_port=config.client_port,
        multicast_ip=config.multicast_ip,
        offer_ttl_s=(
            config.offer_ttl_s
            if config.offer_ttl_s is not None
            else service.deployment.offer_ttl_s
        ),
        find_ttl_s=(
            config.find_ttl_s
            if config.find_ttl_s is not None
            else service.deployment.find_ttl_s
        ),
    )


def _eventgroup_hex(eventgroup_id: int | None) -> str | None:
    if eventgroup_id is None:
        return None
    return f"0x{eventgroup_id:04X}"


def _field_part_id_hex(part: FieldPartDefinition | None) -> str:
    if part is None:
        return "missing"
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


def _format_endpoint(ip_address: str, port: int | None) -> str:
    if not ip_address or port is None:
        return ""
    return f"{ip_address}:{port}"
