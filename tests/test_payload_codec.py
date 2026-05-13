import math

from someip_gui_tool.codec.payload_codec import PayloadCodec
from someip_gui_tool.parsing.service_json import load_service_definition


def _first_param(service, element_name):
    for collection in (service.methods, service.events):
        for element in collection:
            if element.name == element_name:
                return element.parameters[0]
    for field in service.fields:
        for part in (field.getter, field.setter, field.notifier):
            if part and part.name == element_name:
                return part.parameters[0]
    raise AssertionError(f"element not found: {element_name}")


def test_enum_encodes_to_underlying_uint8(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080D.json")
    param = _first_param(service, "SecondStartPopup")

    encoded = PayloadCodec().encode_parameters([param], {"SecondStartPopup": 2})

    assert encoded == b"\x02"


def test_float_struct_round_trip(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080E.json")
    param = _first_param(service, "VehicleInfo")
    codec = PayloadCodec()

    encoded = codec.encode_parameters([param], {"VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}})
    decoded = codec.decode_parameters([param], encoded)

    assert math.isclose(decoded["VehicleInfo"]["VehicleSpeed"], 12.5, rel_tol=0.0001)
    assert math.isclose(decoded["VehicleInfo"]["Odometer"], 99.25, rel_tol=0.0001)


def test_uint8_array_encodes_all_values(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080A.json")
    param = _first_param(service, "IntellgntSwtDecoupSts")

    encoded = PayloadCodec().encode_parameters([param], {"IntellgntSwtDecoupSts": [1, 2, 255]})

    assert encoded == b"\x01\x02\xff"


def test_string_encodes_utf8(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x0F01.json")
    param = _first_param(service, "SlotIDReport")

    encoded = PayloadCodec().encode_parameters([param], {"SlotID": "A12"})

    assert encoded == b"A12"
