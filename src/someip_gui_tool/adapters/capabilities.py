from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class BackendCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"


class BackendOperation(StrEnum):
    UDP_FF_METHOD = "udp-ff-method"
    TCP_FF_METHOD = "tcp-method"
    RR_METHOD = "rr-method"
    UDP_EVENT = "udp-event"
    TCP_EVENT = "tcp-event"
    FIELD_GETTER = "field-getter"
    FIELD_NOTIFIER = "field-notifier"
    FIELD_GETTER_NOTIFIER = "field-getter-notifier"
    SOMEIPYD_PROCESS = "someipyd-process"


SOMEIPY_FF_LIMITATION = (
    "someipy local loopback proves availability for fire-and-forget methods, "
    "but the current adapter path cannot confirm that an FF request was "
    "transmitted and handled end-to-end."
)


@dataclass(frozen=True)
class BackendCapabilityReport:
    backend: str
    operation_status: Mapping[BackendOperation, BackendCapabilityStatus]
    notes: Mapping[BackendOperation, str]
    recommendation: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_status",
            MappingProxyType(dict(self.operation_status)),
        )
        object.__setattr__(self, "notes", MappingProxyType(dict(self.notes)))


def someipy_capability_report() -> BackendCapabilityReport:
    return BackendCapabilityReport(
        backend="someipy",
        operation_status={
            BackendOperation.UDP_FF_METHOD: BackendCapabilityStatus.LIMITED,
            BackendOperation.TCP_FF_METHOD: BackendCapabilityStatus.LIMITED,
            BackendOperation.RR_METHOD: BackendCapabilityStatus.UNSUPPORTED,
            BackendOperation.UDP_EVENT: BackendCapabilityStatus.SUPPORTED,
            BackendOperation.TCP_EVENT: BackendCapabilityStatus.SUPPORTED,
            BackendOperation.FIELD_GETTER: BackendCapabilityStatus.SUPPORTED,
            BackendOperation.FIELD_NOTIFIER: BackendCapabilityStatus.SUPPORTED,
            BackendOperation.FIELD_GETTER_NOTIFIER: BackendCapabilityStatus.SUPPORTED,
            BackendOperation.SOMEIPYD_PROCESS: BackendCapabilityStatus.SUPPORTED,
        },
        notes={
            BackendOperation.UDP_FF_METHOD: SOMEIPY_FF_LIMITATION,
            BackendOperation.TCP_FF_METHOD: SOMEIPY_FF_LIMITATION,
            BackendOperation.RR_METHOD: (
                "RR method execution is not enabled until a matching RR fixture "
                "and adapter request/response path are available."
            ),
            BackendOperation.UDP_EVENT: (
                "Local loopback confirmed UDP event subscribe, send, and callback delivery."
            ),
            BackendOperation.TCP_EVENT: (
                "Local loopback confirmed TCP event subscribe, send, and callback delivery."
            ),
            BackendOperation.FIELD_GETTER: "Local loopback confirmed getter request and response payload.",
            BackendOperation.FIELD_NOTIFIER: (
                "Local loopback confirmed notifier subscribe, send, and callback delivery."
            ),
            BackendOperation.FIELD_GETTER_NOTIFIER: (
                "Local loopback confirmed combined field getter and notifier scenario."
            ),
            BackendOperation.SOMEIPYD_PROCESS: (
                "The application can start, connect to, and stop someipyd."
            ),
        },
        recommendation=(
            "Use someipy for event and field Phase A runtime work. Keep method "
            "operations behind the adapter and run a backend decision gate before "
            "claiming FF method support in the GUI."
        ),
    )
