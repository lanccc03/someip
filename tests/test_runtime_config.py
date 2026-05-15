from someip_gui_tool.core.runtime_config import (
    RuntimeServiceConfig,
    infer_runtime_config,
    validate_runtime_config,
)
from someip_gui_tool.domain.enums import Role
from someip_gui_tool.parsing.service_json import load_service_definition


def test_infer_runtime_config_uses_role_based_ips(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    config = infer_runtime_config(service, Role.SERVER)

    assert config.role is Role.SERVER
    assert config.local_ip == service.deployment.server_ip
    assert config.remote_ip == service.deployment.client_ip
    assert config.multicast_ip == service.deployment.multicast_ip
    assert config.instance_id == service.deployment.instance_id


def test_validate_runtime_config_requires_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = infer_runtime_config(service, Role.SERVER)

    problems = validate_runtime_config(service, config)

    assert [problem.code for problem in problems] == ["server_port_missing", "client_port_missing"]
    assert all(problem.severity == "error" for problem in problems)


def test_validate_runtime_config_accepts_configured_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=Role.CLIENT,
        local_ip=service.deployment.client_ip,
        remote_ip=service.deployment.server_ip,
        server_port=30500,
        client_port=30501,
        multicast_ip=service.deployment.multicast_ip,
    )

    assert validate_runtime_config(service, config) == []
