from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BackendCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"


SOMEIPY_FF_LIMITATION = (
    "someipy local loopback proves availability for fire-and-forget methods, "
    "but the current adapter path cannot confirm that an FF request was "
    "transmitted and handled end-to-end."
)


@dataclass(frozen=True)
class BackendCapabilityReport:
    backend: str
    operation_status: dict[str, BackendCapabilityStatus]
    notes: dict[str, str]
    recommendation: str


def someipy_capability_report() -> BackendCapabilityReport:
    return BackendCapabilityReport(
        backend="someipy",
        operation_status={
            "udp_ff_method": BackendCapabilityStatus.LIMITED,
            "tcp_ff_method": BackendCapabilityStatus.LIMITED,
            "udp_event": BackendCapabilityStatus.SUPPORTED,
            "tcp_event": BackendCapabilityStatus.SUPPORTED,
            "field_getter": BackendCapabilityStatus.SUPPORTED,
            "field_notifier": BackendCapabilityStatus.SUPPORTED,
            "someipyd_process": BackendCapabilityStatus.SUPPORTED,
        },
        notes={
            "udp_ff_method": SOMEIPY_FF_LIMITATION,
            "tcp_ff_method": SOMEIPY_FF_LIMITATION,
            "udp_event": "Local loopback confirmed UDP event subscribe, send, and callback delivery.",
            "tcp_event": "Local loopback confirmed TCP event subscribe, send, and callback delivery.",
            "field_getter": "Local loopback confirmed getter request and response payload.",
            "field_notifier": "Local loopback confirmed notifier subscribe, send, and callback delivery.",
            "someipyd_process": "The application can start, connect to, and stop someipyd.",
        },
        recommendation=(
            "Use someipy for event and field Phase A runtime work. Keep method "
            "operations behind the adapter and run a backend decision gate before "
            "claiming FF method support in the GUI."
        ),
    )
