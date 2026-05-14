from __future__ import annotations

from pathlib import Path

from someip_gui_tool.codec.payload_codec import PayloadCodec
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
            data={
                "service_id": scenario.service.service_id_hex,
                "payload_hex": payload.hex(),
            },
        )

    def _encode_payload(self, scenario: ProtocolScenario) -> bytes:
        values = scenario.payload_values
        if scenario.method is not None:
            return self.codec.encode_parameters(scenario.method.parameters, values)
        if scenario.event is not None:
            return self.codec.encode_parameters(scenario.event.parameters, values)
        if scenario.field is not None and scenario.field.notifier is not None:
            return self.codec.encode_parameters(scenario.field.notifier.parameters, values)
        raise ValueError(f"Scenario has no encodable element: {scenario.kind.value}")
