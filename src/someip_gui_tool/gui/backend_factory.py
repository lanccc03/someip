from __future__ import annotations

import os
from dataclasses import dataclass

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.adapters.someipy_adapter import SomeipyAdapter
from someip_gui_tool.core.runtime_environment import RuntimeEnvironmentProbe
from someip_gui_tool.core.runtime_session import RuntimeSession


@dataclass(frozen=True)
class BackendSettings:
    backend: str = "mock"
    local_ip: str = "127.0.0.1"
    base_port: int = 30500
    start_daemon: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> BackendSettings:
        source = os.environ if environ is None else environ
        return cls(
            backend=source.get("SOMEIP_GUI_BACKEND", "mock").strip().lower(),
            local_ip=source.get("SOMEIP_GUI_LOCAL_IP", "127.0.0.1").strip(),
            base_port=int(source.get("SOMEIP_GUI_BASE_PORT", "30500")),
            start_daemon=_env_flag(source.get("SOMEIP_GUI_START_DAEMON", "")),
        )


def create_session(settings: BackendSettings | None = None) -> RuntimeSession:
    resolved = settings or BackendSettings.from_env()
    environment = RuntimeEnvironmentProbe()
    if resolved.backend == "mock":
        return RuntimeSession(MockSomeIpAdapter(), environment=environment)
    if resolved.backend == "someipy":
        return RuntimeSession(
            SomeipyAdapter(
                local_ip=resolved.local_ip,
                base_port=resolved.base_port,
                start_daemon=resolved.start_daemon,
            ),
            environment=environment,
        )
    raise ValueError(f"Unsupported backend: {resolved.backend!r}")


def _env_flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
