from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_interface
from types import MappingProxyType
from typing import Protocol

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import ServiceDefinition


class RuntimeEnvironment(Protocol):
    def local_ip_addresses(self) -> set[str]:
        ...

    def is_port_available(self, ip_address: str, port: int) -> bool:
        ...


@dataclass(frozen=True)
class RuntimeProblem:
    code: str
    severity: str
    message: str
    service_id: int


@dataclass(frozen=True)
class RuntimeServiceConfig:
    service_id: int
    instance_id: int
    role: Role
    local_ip: str
    remote_ip: str
    server_port: int | None = None
    client_port: int | None = None
    multicast_ip: str = ""
    transport_override: TransportProtocol | None = None
    offer_ttl_s: float | None = None
    find_ttl_s: float | None = None
    payload_defaults: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload_defaults",
            _freeze_payload_default(self.payload_defaults),
        )


def infer_runtime_config(service: ServiceDefinition, role: Role) -> RuntimeServiceConfig:
    return RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=role,
        local_ip=service.deployment.local_ip_for(role),
        remote_ip=service.deployment.remote_ip_for(role),
        multicast_ip=service.deployment.multicast_ip,
        offer_ttl_s=service.deployment.offer_ttl_s,
        find_ttl_s=service.deployment.find_ttl_s,
    )


def validate_runtime_config(
    service: ServiceDefinition,
    config: RuntimeServiceConfig,
    *,
    environment: RuntimeEnvironment | None = None,
) -> list[RuntimeProblem]:
    problems: list[RuntimeProblem] = []
    if config.service_id != service.service_id:
        problems.append(
            RuntimeProblem(
                code="service_id_mismatch",
                severity="error",
                message=(
                    "Runtime config service_id "
                    f"{config.service_id} does not match service definition "
                    f"{service.service_id}."
                ),
                service_id=service.service_id,
            )
        )
    if config.instance_id != service.deployment.instance_id:
        problems.append(
            RuntimeProblem(
                code="instance_id_mismatch",
                severity="error",
                message=(
                    "Runtime config instance_id "
                    f"{config.instance_id} does not match service definition "
                    f"{service.deployment.instance_id}."
                ),
                service_id=service.service_id,
            )
        )
    if config.server_port is None:
        problems.append(
            RuntimeProblem(
                code="server_port_missing",
                severity="error",
                message="Server port must be configured before service start.",
                service_id=service.service_id,
            )
        )
    elif not _is_valid_port(config.server_port):
        problems.append(
            RuntimeProblem(
                code="server_port_invalid",
                severity="error",
                message=(
                    f"Server port {config.server_port} is outside the valid "
                    "range 1..65535."
                ),
                service_id=service.service_id,
            )
        )
    if config.client_port is None:
        problems.append(
            RuntimeProblem(
                code="client_port_missing",
                severity="error",
                message="Client port must be configured before service start.",
                service_id=service.service_id,
            )
        )
    elif not _is_valid_port(config.client_port):
        problems.append(
            RuntimeProblem(
                code="client_port_invalid",
                severity="error",
                message=(
                    f"Client port {config.client_port} is outside the valid "
                    "range 1..65535."
                ),
                service_id=service.service_id,
            )
        )
    local_ip = config.local_ip.strip()
    if not local_ip:
        problems.append(
            RuntimeProblem(
                code="local_ip_missing",
                severity="error",
                message="Local IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    elif not _is_valid_ip(local_ip):
        problems.append(
            RuntimeProblem(
                code="local_ip_invalid",
                severity="error",
                message=f"Local IP {config.local_ip!r} is not a valid IP address.",
                service_id=service.service_id,
            )
        )
    remote_ip = config.remote_ip.strip()
    if not remote_ip:
        problems.append(
            RuntimeProblem(
                code="remote_ip_missing",
                severity="error",
                message="Remote IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    elif not _is_valid_ip(remote_ip):
        problems.append(
            RuntimeProblem(
                code="remote_ip_invalid",
                severity="error",
                message=f"Remote IP {config.remote_ip!r} is not a valid IP address.",
                service_id=service.service_id,
            )
        )
    multicast_ip = config.multicast_ip.strip()
    if not multicast_ip:
        problems.append(
            RuntimeProblem(
                code="multicast_ip_missing",
                severity="warning",
                message="Multicast IP is empty; service discovery may not work.",
                service_id=service.service_id,
            )
        )
    elif not _is_valid_ip(multicast_ip):
        problems.append(
            RuntimeProblem(
                code="multicast_ip_invalid",
                severity="warning",
                message=f"Multicast IP {config.multicast_ip!r} is not a valid IP address.",
                service_id=service.service_id,
            )
        )
    has_error = any(problem.severity == "error" for problem in problems)
    if environment is not None and not has_error:
        local_host = config.local_ip.split("/", 1)[0]
        local_ips = environment.local_ip_addresses()
        if local_host not in local_ips:
            problems.append(
                RuntimeProblem(
                    code="local_ip_not_on_adapter",
                    severity="error",
                    message=f"Local IP {local_host!r} was not found on local network adapters.",
                    service_id=service.service_id,
                )
            )
        if config.server_port is not None and not environment.is_port_available(local_host, config.server_port):
            problems.append(
                RuntimeProblem(
                    code="server_port_occupied",
                    severity="error",
                    message=f"Server port {config.server_port} is already occupied on {local_host}.",
                    service_id=service.service_id,
                )
            )
        if config.client_port is not None and not environment.is_port_available(local_host, config.client_port):
            problems.append(
                RuntimeProblem(
                    code="client_port_occupied",
                    severity="error",
                    message=f"Client port {config.client_port} is already occupied on {local_host}.",
                    service_id=service.service_id,
                )
            )
    return problems


def _is_valid_port(port: int) -> bool:
    return 1 <= port <= 65535


def _is_valid_ip(value: str) -> bool:
    try:
        ip_interface(value)
    except ValueError:
        return False
    return True


def _freeze_payload_default(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_payload_default(nested) for key, nested in value.items()}
        )
    if isinstance(value, list | tuple):
        return tuple(_freeze_payload_default(nested) for nested in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze_payload_default(nested) for nested in value)
    return value
