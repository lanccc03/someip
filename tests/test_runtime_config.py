import pytest

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


def test_infer_runtime_config_uses_client_role_ips(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    config = infer_runtime_config(service, Role.CLIENT)

    assert config.role is Role.CLIENT
    assert config.local_ip == service.deployment.client_ip
    assert config.remote_ip == service.deployment.server_ip


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


def test_validate_runtime_config_rejects_id_mismatches(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = RuntimeServiceConfig(
        service_id=service.service_id + 1,
        instance_id=service.deployment.instance_id + 1,
        role=Role.CLIENT,
        local_ip=service.deployment.client_ip,
        remote_ip=service.deployment.server_ip,
        server_port=30500,
        client_port=30501,
        multicast_ip=service.deployment.multicast_ip,
    )

    problems = validate_runtime_config(service, config)

    assert [problem.code for problem in problems] == [
        "service_id_mismatch",
        "instance_id_mismatch",
    ]
    assert all(problem.severity == "error" for problem in problems)
    assert str(config.service_id) in problems[0].message
    assert str(service.service_id) in problems[0].message
    assert str(config.instance_id) in problems[1].message
    assert str(service.deployment.instance_id) in problems[1].message


def test_validate_runtime_config_rejects_invalid_ports(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=Role.CLIENT,
        local_ip=service.deployment.client_ip,
        remote_ip=service.deployment.server_ip,
        server_port=0,
        client_port=65536,
        multicast_ip=service.deployment.multicast_ip,
    )

    problems = validate_runtime_config(service, config)

    assert [problem.code for problem in problems] == [
        "server_port_invalid",
        "client_port_invalid",
    ]
    assert all(problem.severity == "error" for problem in problems)


def test_validate_runtime_config_rejects_blank_ips_and_multicast(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    config = RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=Role.CLIENT,
        local_ip=" ",
        remote_ip="\t",
        server_port=30500,
        client_port=30501,
        multicast_ip="  ",
    )

    problems = validate_runtime_config(service, config)

    assert [problem.code for problem in problems] == [
        "local_ip_missing",
        "remote_ip_missing",
        "multicast_ip_missing",
    ]
    assert [problem.severity for problem in problems] == ["error", "error", "warning"]


def test_runtime_service_config_payload_defaults_are_immutable(adc40_soc_dir) -> None:
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    defaults = {"counter": 1}
    config = RuntimeServiceConfig(
        service_id=service.service_id,
        instance_id=service.deployment.instance_id,
        role=Role.CLIENT,
        local_ip=service.deployment.client_ip,
        remote_ip=service.deployment.server_ip,
        payload_defaults=defaults,
    )

    defaults["counter"] = 2

    assert config.payload_defaults["counter"] == 1
    with pytest.raises(TypeError):
        config.payload_defaults["counter"] = 3
