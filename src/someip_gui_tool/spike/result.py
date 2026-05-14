from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SpikeStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class SpikeStepResult:
    name: str
    status: SpikeStatus
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        return f"{self.status.value} {self.name} - {self.detail}"


@dataclass(frozen=True)
class SpikeReport:
    name: str
    steps: list[SpikeStepResult]

    @property
    def failed(self) -> bool:
        return any(step.status is SpikeStatus.FAIL for step in self.steps)

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
                    "data": step.data,
                }
                for step in self.steps
            ],
        }
