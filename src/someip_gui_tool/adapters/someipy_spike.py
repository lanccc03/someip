from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class SomeipyAvailability:
    available: bool
    detail: str


def check_someipy_available() -> SomeipyAvailability:
    spec = importlib.util.find_spec("someipy")
    if spec is None:
        return SomeipyAvailability(
            available=False,
            detail="someipy is not installed. Install with: python -m pip install -e .[someipy]",
        )
    return SomeipyAvailability(available=True, detail="someipy import is available")


def describe_spike_plan() -> list[str]:
    return [
        "Start or connect to someipyd",
        "Run UDP FF method with 0x080D SecondStartCtrl",
        "Run TCP method with 0x0F01 AudioRecPopupReq",
        "Run UDP cycle event with 0x080E VehicleInfo",
        "Run TCP trigger event with 0x080A or 0x0F01",
        "Run Field Getter/Notifier with 0x080C VertHeiRmdSts",
        "Package minimal scenario with PyInstaller or Nuitka",
    ]
