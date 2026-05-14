from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType
from typing import Callable


REQUIRED_SOMEIPY_SYMBOLS = (
    "ServiceBuilder",
    "Method",
    "Event",
    "EventGroup",
    "TransportLayerProtocol",
    "ClientServiceInstance",
    "ServerServiceInstance",
    "connect_to_someipy_daemon",
)


@dataclass(frozen=True)
class SomeipyApiStatus:
    available: bool
    detail: str
    missing_symbols: tuple[str, ...] = ()


class SomeipyApiProbe:
    def __init__(self, importer: Callable[[str], object] | None = None) -> None:
        self._importer = importer or importlib.import_module
        self._module: object | None = None

    def probe(self) -> SomeipyApiStatus:
        try:
            module = self._importer("someipy")
        except ModuleNotFoundError:
            return SomeipyApiStatus(
                available=False,
                detail="someipy is not installed. Install with: python -m pip install -e .[someipy]",
            )

        missing = tuple(name for name in REQUIRED_SOMEIPY_SYMBOLS if not hasattr(module, name))
        if missing:
            return SomeipyApiStatus(
                available=False,
                detail="someipy API missing required symbols: " + ", ".join(missing),
                missing_symbols=missing,
            )
        self._module = module
        return SomeipyApiStatus(available=True, detail="someipy API is available")

    def require_module(self) -> ModuleType:
        if self._module is None:
            status = self.probe()
            if not status.available:
                raise RuntimeError(status.detail)
        return self._module  # type: ignore[return-value]
