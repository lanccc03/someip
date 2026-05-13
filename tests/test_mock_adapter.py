import pytest

from someip_gui_tool.adapters.mock import MockSomeIpAdapter
from someip_gui_tool.parsing.service_json import load_service_definition


@pytest.mark.asyncio
async def test_mock_adapter_records_method_and_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    adapter = MockSomeIpAdapter()

    await adapter.start_service(service)
    await adapter.call_method(service, service.methods[0], b"\x01")
    await adapter.publish_event(service, service.events[0], b"\x02")
    await adapter.stop_service(service)

    assert [call.name for call in adapter.calls] == [
        "start_service",
        "call_method",
        "publish_event",
        "stop_service",
    ]
