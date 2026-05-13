from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.domain.models import DeploymentConfig, ServiceDefinition


def test_service_definition_model_accepts_hex_ids():
    deployment = DeploymentConfig(
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
