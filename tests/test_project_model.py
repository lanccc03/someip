from pathlib import Path

from someip_gui_tool.domain.enums import Role, TransportProtocol
from someip_gui_tool.project.project_model import (
    ProjectFile,
    ServiceRuntimeOverride,
)


def test_project_file_round_trip():
    project = ProjectFile(
        schema_version="1.0",
        project_name="ADC40_SOC manual test",
        definition_root=Path("ADC40_SOC"),
        services={
            "0x080D": ServiceRuntimeOverride(
                enabled=True,
                role=Role.CLIENT,
                local_ip="172.16.2.99/24",
                remote_ip="172.16.2.14/24",
                server_port=30501,
                client_port=0,
                multicast_ip="239.192.255.251",
                transport=TransportProtocol.UDP,
            )
        },
        sequences=[],
    )

    restored = ProjectFile.model_validate_json(project.model_dump_json())

    assert restored.services["0x080D"].role is Role.CLIENT
    assert restored.services["0x080D"].server_port == 30501
