from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from os import PathLike
from typing import Any


class SpikeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class SpikeStepResult:
    name: str
    status: SpikeStatus | str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            status = SpikeStatus(self.status)
        except ValueError as exc:
            raise ValueError(f"Invalid spike status: {self.status!r}") from exc
        object.__setattr__(self, "status", status)

    def as_text(self) -> str:
        return f"{self.status.value} {self.name} - {self.detail}"


@dataclass(frozen=True)
class SpikeReport:
    name: str
    steps: list[SpikeStepResult]

    @property
    def failed(self) -> bool:
        return any(step.status == SpikeStatus.FAIL for step in self.steps)

    def as_text(self) -> str:
        lines = [f"Spike report: {self.name}"]
        lines.extend(step.as_text() for step in self.steps)
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "failed": self.failed,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "detail": step.detail,
                    "data": _json_safe(step.data),
                }
                for step in self.steps
            ],
        }


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, PathLike):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, dict):
        return {_json_safe_key(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _json_safe_key(value: Any) -> str | int | float | bool | None:
    safe = _json_safe(value)
    if safe is None or isinstance(safe, (str, int, float, bool)):
        return safe
    return str(safe)
