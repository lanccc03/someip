import json

from someip_gui_tool.gui.payload_defaults import default_payload_values, payload_values_json
from someip_gui_tool.parsing.service_json import load_service_definition


def test_default_payload_values_for_uint8_method(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")

    values = default_payload_values(service.methods[0].parameters)

    assert values == {"SecondStartCtrlCmd": 0}


def test_default_payload_values_for_struct_event(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")

    values = default_payload_values(service.events[0].parameters)

    assert values == {"VehicleInfo": {"VehicleSpeed": 0.0, "Odometer": 0.0}}


def test_payload_values_json_is_stable_and_pretty(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")
    field = service.fields[0]
    assert field.notifier is not None

    text = payload_values_json(field.notifier.parameters)

    assert json.loads(text) == {"VertHeiRmdSts": 0}
    assert text.endswith("\n")
