from someip_gui_tool.adapters.capabilities import (
    BackendOperation,
    BackendCapabilityStatus,
    someipy_capability_report,
)


EXPECTED_OPERATIONS = {
    BackendOperation.UDP_FF_METHOD,
    BackendOperation.TCP_FF_METHOD,
    BackendOperation.RR_METHOD,
    BackendOperation.UDP_EVENT,
    BackendOperation.TCP_EVENT,
    BackendOperation.FIELD_GETTER,
    BackendOperation.FIELD_NOTIFIER,
    BackendOperation.FIELD_GETTER_NOTIFIER,
    BackendOperation.SOMEIPYD_PROCESS,
}


def test_someipy_report_covers_all_backend_operations_with_notes() -> None:
    report = someipy_capability_report()

    assert set(report.operation_status) == EXPECTED_OPERATIONS
    assert set(report.notes) == EXPECTED_OPERATIONS
    assert all(note.strip() for note in report.notes.values())


def test_someipy_report_mappings_are_immutable() -> None:
    report = someipy_capability_report()

    try:
        report.operation_status[BackendOperation.UDP_EVENT] = BackendCapabilityStatus.UNSUPPORTED
    except TypeError:
        pass
    else:
        raise AssertionError("operation status mapping should be immutable")


def test_someipy_report_marks_proven_event_and_field_paths() -> None:
    report = someipy_capability_report()

    assert report.backend == "someipy"
    assert report.operation_status[BackendOperation.UDP_EVENT] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status[BackendOperation.TCP_EVENT] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status[BackendOperation.FIELD_GETTER] is BackendCapabilityStatus.SUPPORTED
    assert report.operation_status[BackendOperation.FIELD_NOTIFIER] is BackendCapabilityStatus.SUPPORTED


def test_someipy_report_marks_ff_methods_as_limited() -> None:
    report = someipy_capability_report()

    assert report.operation_status[BackendOperation.UDP_FF_METHOD] is BackendCapabilityStatus.LIMITED
    assert report.operation_status[BackendOperation.TCP_FF_METHOD] is BackendCapabilityStatus.LIMITED
    assert "fire-and-forget" in report.notes[BackendOperation.UDP_FF_METHOD]
    assert "backend decision gate" in report.recommendation.lower()
