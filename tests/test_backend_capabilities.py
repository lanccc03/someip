from someip_gui_tool.adapters.capabilities import (
    BackendCapabilityStatus,
    someipy_capability_report,
)


def test_someipy_report_marks_proven_event_and_field_paths() -> None:
    report = someipy_capability_report()

    assert report.backend == "someipy"
    assert report.operation_status["udp_event"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["tcp_event"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["field_getter"] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status["field_notifier"] is BackendCapabilityStatus.SUPPORTED


def test_someipy_report_marks_ff_methods_as_limited() -> None:
    report = someipy_capability_report()

    assert report.operation_status["udp_ff_method"] is BackendCapabilityStatus.LIMITED
    assert report.operation_status["tcp_ff_method"] is BackendCapabilityStatus.LIMITED
    assert "fire-and-forget" in report.notes["udp_ff_method"]
    assert "backend decision gate" in report.recommendation.lower()
