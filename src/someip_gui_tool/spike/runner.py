from __future__ import annotations

from pathlib import Path
from typing import Any

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
