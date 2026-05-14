import json
from pathlib import Path

import pytest

from someip_gui_tool.spike.result import SpikeReport, SpikeStatus, SpikeStepResult


def test_report_failed_is_true_when_any_step_fails():
    report = SpikeReport(
        name="protocol-spike",
        steps=[
            SpikeStepResult(name="api", status=SpikeStatus.PASS, detail="api ok"),
            SpikeStepResult(name="tcp-method", status=SpikeStatus.FAIL, detail="connection failed"),
        ],
    )

    assert report.failed is True
    text = report.as_text()
    assert "protocol-spike" in text
    assert "PASS api - api ok" in text
    assert "FAIL tcp-method - connection failed" in text


def test_report_failed_is_false_for_pass_and_skip():
    report = SpikeReport(
        name="protocol-spike",
        steps=[
            SpikeStepResult(name="api", status=SpikeStatus.PASS, detail="api ok"),
            SpikeStepResult(name="real-run", status=SpikeStatus.SKIP, detail="someipy missing"),
        ],
    )

    assert report.failed is False


def test_step_accepts_string_status_values():
    report = SpikeReport(
        name="protocol-spike",
        steps=[SpikeStepResult(name="tcp-method", status="FAIL", detail="connection failed")],
    )

    assert report.failed is True
    assert report.steps[0].status is SpikeStatus.FAIL


def test_step_rejects_invalid_status_values():
    with pytest.raises(ValueError):
        SpikeStepResult(name="tcp-method", status="BROKEN", detail="connection failed")


def test_report_as_dict_serializes_bytes_and_paths():
    definition_path = Path("ADC40_SOC/0x080D.json")
    report = SpikeReport(
        name="protocol-spike",
        steps=[
            SpikeStepResult(
                name="api",
                status=SpikeStatus.PASS,
                detail="api ok",
                data={"payload": b"\x01\x02", "definition": definition_path},
            )
        ],
    )

    payload = report.as_dict()

    json.dumps(payload)
    assert payload["steps"][0]["data"] == {
        "payload": "0102",
        "definition": str(definition_path),
    }
