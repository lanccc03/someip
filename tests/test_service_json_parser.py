from dataclasses import replace

import pytest

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import DeploymentConfig, ServiceDefinition
from someip_gui_tool.parsing.service_json import (
    load_service_definition,
    load_service_directory,
)
from someip_gui_tool.core.service_registry import ServiceRegistry


def build_deployment_config() -> DeploymentConfig:
    return DeploymentConfig(
        instance_id=0x0001,
        major_version=1,
        minor_version=0,
        server_ecu="ADC40_SOC",
        server_ip="172.16.3.14/24",
        client_ecu="HUT_SOC_Android",
        client_ip="172.16.3.99/24",
        multicast_ip="239.192.255.251",
        vlan_id=3,
        vlan_priority=3,
        default_transport=TransportProtocol.TCP,
        offer_ttl_s=3.0,
        find_ttl_s=3.0,
    )


def test_service_definition_model_accepts_hex_ids():
    deployment = build_deployment_config()
    service = ServiceDefinition(
        service_id=0x080A,
        service_name="CockpitIntellgntDecouplingSrv",
        deployment=deployment,
        methods=[],
        events=[],
        fields=[],
    )

    assert service.service_id_hex == "0x080A"
    assert service.deployment.local_ip_for(Role.SERVER) == "172.16.3.14/24"
    assert service.deployment.local_ip_for(Role.CLIENT) == "172.16.3.99/24"


def test_deployment_config_accepts_string_roles():
    deployment = build_deployment_config()

    assert deployment.local_ip_for("Server") == "172.16.3.14/24"
    assert deployment.local_ip_for("Client") == "172.16.3.99/24"
    assert deployment.remote_ip_for("Server") == "172.16.3.99/24"
    assert deployment.remote_ip_for("Client") == "172.16.3.14/24"


def test_deployment_config_rejects_invalid_role():
    deployment = build_deployment_config()

    with pytest.raises(ValueError, match="Unsupported role: 'Invalid'"):
        deployment.local_ip_for("Invalid")

    with pytest.raises(ValueError, match="Unsupported role: 'Invalid'"):
        deployment.remote_ip_for("Invalid")


def test_load_second_start_service(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    assert service.service_id == 0x080D
    assert service.service_name == "SecondStartSrv"
    assert service.deployment.instance_id == 0x0001
    assert service.deployment.default_transport.value == "UDP"
    assert [event.name for event in service.events] == ["SecondStartPopup"]
    assert [method.name for method in service.methods] == ["SecondStartCtrl"]
    assert service.methods[0].method_id == 0x0001
    assert service.events[0].eventgroup_id == 0x0001


def test_load_service_directory_includes_all_json(adc40_soc_dir):
    services = load_service_directory(adc40_soc_dir)
    ids = {service.service_id for service in services}

    assert {0x080A, 0x080C, 0x080D, 0x080E, 0x0F01}.issubset(ids)


def test_service_registry_loads_and_queries(adc40_soc_dir):
    registry = ServiceRegistry.load_directory(adc40_soc_dir)

    service = registry.get_service(0x080C)

    assert service.service_name == "IntelliDriveRmdSrv"
    assert registry.find_element(0x080C, 0x9001).name == "VertHeiRmdSts"


def test_service_registry_rejects_duplicate_service_id(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    with pytest.raises(ValueError, match="Duplicate service id 0x080C"):
        ServiceRegistry([service, replace(service)])


def test_service_registry_rejects_duplicate_element_id(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    duplicate_getter = replace(field.getter, element_id=0x9001)
    duplicate_field = replace(field, getter=duplicate_getter)
    duplicate_service = replace(service, fields=[duplicate_field])
    registry = ServiceRegistry([duplicate_service])

    with pytest.raises(
        ValueError,
        match="Duplicate element id 0x9001 in service 0x080C",
    ):
        registry.find_element(0x080C, 0x9001)


def test_service_registry_missing_element_error_uses_hex_ids(adc40_soc_dir):
    registry = ServiceRegistry.load_directory(adc40_soc_dir)

    with pytest.raises(KeyError) as exc_info:
        registry.find_element(0x080C, 0x9999)

    message = str(exc_info.value)
    assert "0x9999" in message
    assert "0x080C" in message
