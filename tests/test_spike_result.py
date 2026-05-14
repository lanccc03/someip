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
