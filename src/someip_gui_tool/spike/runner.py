from __future__ import annotations

import asyncio
import inspect
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess
from someip_gui_tool.adapters.someipy_mapping import (
    FIRE_AND_FORGET_LIMITATION,
    SomeipyServiceFactory,
)
from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.domain.models import format_hex
from someip_gui_tool.spike.result import SpikeReport, SpikeStatus, SpikeStepResult
from someip_gui_tool.spike.scenarios import ProtocolScenario, build_scenarios


REAL_RUN_AVAILABILITY_ATTEMPTS = 3
REAL_RUN_AVAILABILITY_DELAY_S = 0.05
REAL_RUN_EVENT_TIMEOUT_S = 0.2


class ProtocolSpikeRunner:
    def __init__(self, definition_root: Path) -> None:
        self.definition_root = definition_root
        self.codec = PayloadCodec()

    def run_dry(self) -> SpikeReport:
        steps = [self._dry_step(scenario) for scenario in build_scenarios(self.definition_root)]
        return SpikeReport(name="someipy-protocol-spike-dry-run", steps=steps)

    def run_real(
        self,
        api_probe: Any | None = None,
        local_ip: str = "127.0.0.1",
        base_port: int = 30500,
        start_daemon: bool = False,
    ) -> SpikeReport:
        probe = api_probe or SomeipyApiProbe()
        status = probe.probe()
        if not status.available:
            return SpikeReport(
                name="someipy-protocol-spike-real-run",
                steps=[
                    SpikeStepResult(
                        name="someipy-api",
                        status=SpikeStatus.SKIP,
                        detail=status.detail,
                    )
                ],
            )

        steps = [
            SpikeStepResult(
                name="someipy-api",
                status=SpikeStatus.PASS,
                detail=status.detail,
            )
        ]
        daemon_process = None
        temp_work_dir = None
        daemon_client_config: dict[str, object] | None = None
        try:
            if start_daemon:
                temp_work_dir = tempfile.TemporaryDirectory(prefix="someipyd-spike-")
                daemon_config = SomeipydConfig(interface=local_ip)
                daemon_process = SomeipydProcess.start(
                    config=daemon_config,
                    work_dir=Path(temp_work_dir.name),
                )
                daemon_client_config = daemon_config.client_config()
                steps.append(
                    SpikeStepResult(
                        name="someipyd",
                        status=SpikeStatus.PASS,
                        detail="someipyd process started",
                    )
                )

            api = probe.require_module()
            steps.extend(
                asyncio.run(
                    self._run_real_async(
                        api=api,
                        local_ip=local_ip,
                        base_port=base_port,
                        daemon_client_config=daemon_client_config,
                    )
                )
            )
        except Exception as exc:
            steps.append(
                SpikeStepResult(
                    name="real-loopback",
                    status=SpikeStatus.FAIL,
                    detail=str(exc),
                )
            )
        finally:
            if daemon_process is not None:
                daemon_process.stop()
            if temp_work_dir is not None:
                temp_work_dir.cleanup()

        return SpikeReport(name="someipy-protocol-spike-real-run", steps=steps)

    async def _run_real_async(
        self,
        api: Any,
        local_ip: str,
        base_port: int,
        daemon_client_config: dict[str, object] | None = None,
    ) -> list[SpikeStepResult]:
        daemon = await _connect_to_someipy_daemon(api, daemon_client_config)
        steps: list[SpikeStepResult] = []
        try:
            for index, scenario in enumerate(build_scenarios(self.definition_root)):
                payload = self._encode_payload(scenario)
                factory = SomeipyServiceFactory(
                    api,
                    method_handler_factory=self._method_handler_factory(api, payload),
                )
                mapped_service = factory.build_service(scenario.service)
                endpoint_port = base_port + index * 10
                server = api.ServerServiceInstance(
                    daemon=daemon,
                    service=mapped_service,
                    instance_id=scenario.service.deployment.instance_id,
                    endpoint_ip=local_ip,
                    endpoint_port=endpoint_port,
                    ttl=int(scenario.service.deployment.offer_ttl_s),
                    cyclic_offer_delay_ms=1000,
                )
                client = api.ClientServiceInstance(
                    daemon=daemon,
                    service=mapped_service,
                    instance_id=scenario.service.deployment.instance_id,
                    endpoint_ip=local_ip,
                    endpoint_port=endpoint_port + 1,
                    client_id=0x1000 + index,
                )

                try:
                    await _maybe_await(server.start_offer())
                    available = await _poll_is_available(client)
                    data = self._step_data(scenario, payload)
                    detail = f"{scenario.title}: availability={available}"
                    if not available:
                        steps.append(
                            SpikeStepResult(
                                name=scenario.kind.value,
                                status=SpikeStatus.FAIL,
                                detail=detail,
                                data=data,
                            )
                        )
                        continue

                    if scenario.method is not None:
                        steps.append(
                            await self._method_step(
                                client=client,
                                scenario=scenario,
                                payload=payload,
                                detail=detail,
                                data=data,
                            )
                        )
                        continue

                    if scenario.event is not None:
                        steps.append(
                            await self._event_step(
                                api=api,
                                factory=factory,
                                client=client,
                                server=server,
                                scenario=scenario,
                                payload=payload,
                                detail=detail,
                                data=data,
                            )
                        )
                        continue

                    if scenario.field is not None:
                        steps.append(
                            await self._field_step(
                                api=api,
                                factory=factory,
                                client=client,
                                server=server,
                                scenario=scenario,
                                payload=payload,
                                detail=detail,
                                data=data,
                            )
                        )
                        continue

                    steps.append(
                        SpikeStepResult(
                            name=scenario.kind.value,
                            status=SpikeStatus.FAIL,
                            detail=f"{detail}, no executable scenario element",
                            data=data,
                        )
                    )
                finally:
                    await _maybe_await(server.stop_offer())
        finally:
            await _disconnect_someipy_daemon(api, daemon)
        return steps

    def _method_handler_factory(self, api: Any, response_payload: bytes) -> Any:
        def handler_factory(service: Any, method_part: Any) -> Any:
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
                result.payload = response_payload
                return result

            return method_handler

        return handler_factory

    async def _method_step(
        self,
        *,
        client: Any,
        scenario: ProtocolScenario,
        payload: bytes,
        detail: str,
        data: dict[str, Any],
    ) -> SpikeStepResult:
        if scenario.method is None:
            raise ValueError("Method step requires a method scenario")
        if scenario.method.rr_ff == "FF":
            data["limitation"] = FIRE_AND_FORGET_LIMITATION
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.SKIP,
                detail=f"{detail}, {FIRE_AND_FORGET_LIMITATION}",
                data=data,
            )

        result = await _maybe_await(client.call_method(scenario.method.method_id, payload))
        response_payload = _method_result_payload(result)
        data.update(
            {
                "request_payload_hex": payload.hex(),
                "response_payload_hex": response_payload.hex(),
            }
        )
        if response_payload != payload:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=(
                    f"{detail}, method response payload mismatch: "
                    f"expected {payload.hex()} got {response_payload.hex()}"
                ),
                data=data,
            )
        return SpikeStepResult(
            name=scenario.kind.value,
            status=SpikeStatus.PASS,
            detail=f"{detail}, method response payload matched ({response_payload.hex()})",
            data=data,
        )

    async def _event_step(
        self,
        *,
        api: Any,
        factory: SomeipyServiceFactory,
        client: Any,
        server: Any,
        scenario: ProtocolScenario,
        payload: bytes,
        detail: str,
        data: dict[str, Any],
    ) -> SpikeStepResult:
        if scenario.event is None or scenario.event.eventgroup_id is None:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=f"{detail}, event has no eventgroup",
                data=data,
            )
        delivered = await self._subscribe_send_and_wait_for_event(
            api=api,
            factory=factory,
            client=client,
            server=server,
            service_find_ttl_s=scenario.service.deployment.find_ttl_s,
            eventgroup_id=scenario.event.eventgroup_id,
            event_id=scenario.event.event_id,
            transport=scenario.event.transport,
            payload=payload,
        )
        return self._delivery_step(
            scenario=scenario,
            delivered=delivered,
            detail=f"{detail}, event payload sent ({payload.hex()})",
            data=data,
        )

    async def _field_step(
        self,
        *,
        api: Any,
        factory: SomeipyServiceFactory,
        client: Any,
        server: Any,
        scenario: ProtocolScenario,
        payload: bytes,
        detail: str,
        data: dict[str, Any],
    ) -> SpikeStepResult:
        if scenario.field is None or scenario.field.getter is None or scenario.field.notifier is None:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=f"{detail}, field is missing getter or notifier",
                data=data,
            )

        getter = scenario.field.getter
        notifier = scenario.field.notifier
        result = await _maybe_await(client.call_method(getter.element_id, payload))
        getter_payload = _method_result_payload(result)
        data["getter_response_payload_hex"] = getter_payload.hex()
        if getter_payload != payload:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=(
                    f"{detail}, getter response payload mismatch: "
                    f"expected {payload.hex()} got {getter_payload.hex()}"
                ),
                data=data,
            )

        if notifier.eventgroup_id is None:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=f"{detail}, notifier has no eventgroup",
                data=data,
            )

        delivered = await self._subscribe_send_and_wait_for_event(
            api=api,
            factory=factory,
            client=client,
            server=server,
            service_find_ttl_s=scenario.service.deployment.find_ttl_s,
            eventgroup_id=notifier.eventgroup_id,
            event_id=notifier.element_id,
            transport=notifier.transport,
            payload=payload,
        )
        return self._delivery_step(
            scenario=scenario,
            delivered=delivered,
            detail=(
                f"{detail}, getter response payload matched ({getter_payload.hex()}), "
                f"notifier payload sent ({payload.hex()})"
            ),
            data=data,
        )

    async def _subscribe_send_and_wait_for_event(
        self,
        *,
        api: Any,
        factory: SomeipyServiceFactory,
        client: Any,
        server: Any,
        service_find_ttl_s: float,
        eventgroup_id: int,
        event_id: int,
        transport: Any,
        payload: bytes,
    ) -> bool:
        received = asyncio.Event()

        def callback(received_event_id: int, received_payload: bytes) -> None:
            if received_event_id == event_id and received_payload == payload:
                received.set()

        register_callback = getattr(client, "register_callback", None)
        if register_callback is not None:
            await _maybe_await(register_callback(callback))

        eventgroup = api.EventGroup(
            id=eventgroup_id,
            events=[
                api.Event(
                    id=event_id,
                    protocol=factory.protocol_for(transport),
                )
            ],
        )
        await _maybe_await(
            client.subscribe_eventgroup(
                eventgroup,
                ttl_subscription_seconds=int(service_find_ttl_s),
            )
        )
        await _maybe_await(server.send_event(eventgroup_id, event_id, payload))
        if register_callback is None:
            return False
        try:
            await asyncio.wait_for(received.wait(), timeout=REAL_RUN_EVENT_TIMEOUT_S)
        except asyncio.TimeoutError:
            return False
        return True

    def _delivery_step(
        self,
        *,
        scenario: ProtocolScenario,
        delivered: bool,
        detail: str,
        data: dict[str, Any],
    ) -> SpikeStepResult:
        if delivered:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.PASS,
                detail=f"{detail}, delivery confirmed",
                data=data,
            )
        return SpikeStepResult(
            name=scenario.kind.value,
            status=SpikeStatus.FAIL,
            detail=f"{detail}, delivery timed out",
            data=data,
        )

    def _dry_step(self, scenario: ProtocolScenario) -> SpikeStepResult:
        try:
            payload = self._encode_payload(scenario)
            data = self._step_data(scenario, payload)
        except Exception as exc:
            return SpikeStepResult(
                name=scenario.kind.value,
                status=SpikeStatus.FAIL,
                detail=f"{scenario.title}: payload encode failed: {exc}",
            )

        return SpikeStepResult(
            name=scenario.kind.value,
            status=SpikeStatus.PASS,
            detail=f"{scenario.title}: encoded {len(payload)} bytes",
            data=data,
        )

    def _encode_payload(self, scenario: ProtocolScenario) -> bytes:
        values = scenario.payload_values
        if scenario.method is not None:
            return self.codec.encode_parameters(scenario.method.parameters, values)
        if scenario.event is not None:
            return self.codec.encode_parameters(scenario.event.parameters, values)
        if scenario.field is not None:
            getter, notifier = scenario.field.getter, scenario.field.notifier
            if getter is None:
                raise ValueError(f"Field {scenario.field.name!r} has no getter")
            if notifier is None:
                raise ValueError(f"Field {scenario.field.name!r} has no notifier")
            if getter.element_id != 0x1001:
                raise ValueError(
                    f"Field {scenario.field.name!r} getter id "
                    f"{format_hex(getter.element_id)} does not match 0x1001"
                )
            if notifier.element_id != 0x9001:
                raise ValueError(
                    f"Field {scenario.field.name!r} notifier id "
                    f"{format_hex(notifier.element_id)} does not match 0x9001"
                )
            getter_payload = self.codec.encode_parameters(getter.parameters, values)
            notifier_payload = self.codec.encode_parameters(notifier.parameters, values)
            if getter_payload != notifier_payload:
                raise ValueError(
                    f"Field {scenario.field.name!r} getter and notifier payloads differ"
                )
            return notifier_payload
        raise ValueError(f"Scenario has no encodable element: {scenario.kind.value}")

    def _step_data(self, scenario: ProtocolScenario, payload: bytes) -> dict[str, Any]:
        data: dict[str, Any] = {
            "service_id": scenario.service.service_id_hex,
            "payload_hex": payload.hex(),
        }
        if scenario.method is not None:
            data.update(
                {
                    "transport": scenario.method.transport.value,
                    "method_id": scenario.method.method_id_hex,
                    "rr_ff": scenario.method.rr_ff,
                }
            )
            return data

        if scenario.event is not None:
            data.update(
                {
                    "transport": scenario.event.transport.value,
                    "event_id": scenario.event.event_id_hex,
                    "send_strategy": (
                        scenario.event.send_strategy.value
                        if scenario.event.send_strategy is not None
                        else None
                    ),
                    "eventgroup_id": _optional_hex(scenario.event.eventgroup_id),
                }
            )
            return data

        if scenario.field is not None:
            getter, notifier = scenario.field.getter, scenario.field.notifier
            if getter is None or notifier is None:
                raise ValueError(f"Field {scenario.field.name!r} is missing getter or notifier")
            data.update(
                {
                    "transport": notifier.transport.value,
                    "getter_id": format_hex(getter.element_id),
                    "notifier_id": format_hex(notifier.element_id),
                    "notifier_eventgroup_id": _optional_hex(notifier.eventgroup_id),
                    "getter_transport": getter.transport.value,
                    "notifier_transport": notifier.transport.value,
                }
            )
            return data

        return data


def _optional_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return format_hex(value)


async def _connect_to_someipy_daemon(
    api: Any,
    daemon_client_config: dict[str, object] | None,
) -> Any:
    connect = api.connect_to_someipy_daemon
    if daemon_client_config:
        supports_config = _supports_config_arg(connect)
        if supports_config is True:
            return await _maybe_await(connect(daemon_client_config))
        if supports_config is None:
            try:
                return await _maybe_await(connect(daemon_client_config))
            except TypeError:
                pass
    return await _maybe_await(connect())


def _supports_config_arg(callable_object: Any) -> bool | None:
    try:
        signature = inspect.signature(callable_object)
    except (TypeError, ValueError):
        return None

    parameters = signature.parameters
    if any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters.values()
    ):
        return True
    config = parameters.get("config")
    if config is None:
        return None if any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ) else False
    return config.kind in {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    }


async def _poll_is_available(
    client: Any,
    attempts: int = REAL_RUN_AVAILABILITY_ATTEMPTS,
    delay_s: float = REAL_RUN_AVAILABILITY_DELAY_S,
) -> bool:
    for attempt in range(attempts):
        if bool(await _maybe_await(client.is_available())):
            return True
        if attempt < attempts - 1 and delay_s > 0:
            await asyncio.sleep(delay_s)
    return False


def _method_result_payload(result: Any) -> bytes:
    payload = getattr(result, "payload", b"")
    if payload is None:
        return b""
    if not isinstance(payload, bytes):
        raise TypeError(f"MethodResult payload must be bytes, got {type(payload).__name__}")
    return payload


async def _disconnect_someipy_daemon(api: Any, daemon: Any) -> None:
    for owner, method_name in (
        (daemon, "disconnect_from_daemon"),
        (daemon, "disconnect_from_someipy_daemon"),
        (daemon, "disconnect"),
        (api, "disconnect_from_someipy_daemon"),
    ):
        disconnect = getattr(owner, method_name, None)
        if disconnect is not None:
            await _maybe_await(disconnect())
            return


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value
