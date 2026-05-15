from __future__ import annotations

from dataclasses import dataclass, field

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import ServiceDefinition


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
    payload_defaults: dict[str, object] = field(default_factory=dict)


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
) -> list[RuntimeProblem]:
    problems: list[RuntimeProblem] = []
    if config.server_port is None:
        problems.append(
            RuntimeProblem(
                code="server_port_missing",
                severity="error",
                message="Server port must be configured before service start.",
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
    if not config.local_ip:
        problems.append(
            RuntimeProblem(
                code="local_ip_missing",
                severity="error",
                message="Local IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if not config.remote_ip:
        problems.append(
            RuntimeProblem(
                code="remote_ip_missing",
                severity="error",
                message="Remote IP must be configured before service start.",
                service_id=service.service_id,
            )
        )
    if not config.multicast_ip:
        problems.append(
            RuntimeProblem(
                code="multicast_ip_missing",
                severity="warning",
                message="Multicast IP is empty; service discovery may not work.",
                service_id=service.service_id,
            )
        )
    return problems
