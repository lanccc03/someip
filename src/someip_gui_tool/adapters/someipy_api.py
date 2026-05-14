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
        self._module = None
        try:
            module = self._importer("someipy")
        except ModuleNotFoundError as exc:
            if exc.name == "someipy":
                return SomeipyApiStatus(
                    available=False,
                    detail="someipy is not installed. Install with: python -m pip install -e .[someipy]",
                )
            return SomeipyApiStatus(
                available=False,
                detail=f"someipy import failed due to missing dependency: {exc.name}",
            )
        except ImportError as exc:
            return SomeipyApiStatus(available=False, detail=f"someipy import failed: {exc}")

        symbol_status = self._probe_required_symbols(module)
        if symbol_status is not None:
            return symbol_status

        self._module = module
        return SomeipyApiStatus(available=True, detail="someipy API is available")

    def _probe_required_symbols(self, module: object) -> SomeipyApiStatus | None:
        missing: list[str] = []
        for name in REQUIRED_SOMEIPY_SYMBOLS:
            try:
                getattr(module, name)
            except AttributeError:
                missing.append(name)
            except ModuleNotFoundError as exc:
                return SomeipyApiStatus(
                    available=False,
                    detail=(
                        f"someipy API symbol {name} import failed due to missing "
                        f"dependency: {exc.name}"
                    ),
                )
            except ImportError as exc:
                return SomeipyApiStatus(
                    available=False,
                    detail=f"someipy API symbol {name} import failed: {exc}",
                )

        missing_symbols = tuple(missing)
        if missing_symbols:
            return SomeipyApiStatus(
                available=False,
                detail="someipy API missing required symbols: " + ", ".join(missing_symbols),
                missing_symbols=missing_symbols,
            )
        return None

    def require_module(self) -> ModuleType:
        if self._module is None:
            status = self.probe()
            if not status.available:
                raise RuntimeError(status.detail)
        return self._module  # type: ignore[return-value]
