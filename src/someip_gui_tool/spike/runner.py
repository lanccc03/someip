from __future__ import annotations

import asyncio
import inspect
import tempfile
from pathlib import Path
from typing import Any

from someip_gui_tool.adapters.someipy_api import SomeipyApiProbe
from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess
from someip_gui_tool.adapters.someipy_mapping import SomeipyServiceFactory
from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.domain.models import format_hex
from someip_gui_tool.spike.result import SpikeReport, SpikeStatus, SpikeStepResult
from someip_gui_tool.spike.scenarios import ProtocolScenario, build_scenarios


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
            factory = SomeipyServiceFactory(api)
            for index, scenario in enumerate(build_scenarios(self.definition_root)):
                payload = self._encode_payload(scenario)
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
                    available = bool(await _maybe_await(client.is_available()))
                    data = self._step_data(scenario, payload)
                    detail = f"{scenario.title}: availability={available}"
                    if scenario.event is not None and scenario.event.eventgroup_id is not None:
                        await self._subscribe_and_send_event(
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
                        detail += f", event payload sent ({payload.hex()})"
                    if scenario.field is not None:
                        getter = scenario.field.getter
                        notifier = scenario.field.notifier
                        if notifier is not None and notifier.eventgroup_id is not None:
                            await self._subscribe_and_send_event(
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
                            getter_id = format_hex(getter.element_id) if getter is not None else "missing"
                            detail += (
                                f", getter {getter_id} validated; "
                                f"notifier payload sent ({payload.hex()})"
                            )
                    steps.append(
                        SpikeStepResult(
                            name=scenario.kind.value,
                            status=SpikeStatus.PASS if available else SpikeStatus.FAIL,
                            detail=detail,
                            data=data,
                        )
                    )
                finally:
                    await _maybe_await(server.stop_offer())
        finally:
            await _disconnect_someipy_daemon(api, daemon)
        return steps

    async def _subscribe_and_send_event(
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
    ) -> None:
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
        supports_kwargs = _supports_kwargs(connect, daemon_client_config)
        if supports_kwargs is True:
            return await _maybe_await(connect(**daemon_client_config))
        if supports_kwargs is None:
            try:
                return await _maybe_await(connect(**daemon_client_config))
            except TypeError:
                pass
    return await _maybe_await(connect())


def _supports_kwargs(callable_object: Any, kwargs: dict[str, object]) -> bool | None:
    try:
        signature = inspect.signature(callable_object)
    except (TypeError, ValueError):
        return None

    parameters = signature.parameters
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return True
    accepted_kinds = {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
    return all(
        name in parameters and parameters[name].kind in accepted_kinds
        for name in kwargs
    )


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
