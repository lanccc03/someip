from someip_gui_tool.parsing.service_json import load_service_definition


def test_groups_getter_and_notifier_by_field_name(adc40_soc_dir):
    service = load_service_definition(adc40_soc_dir / "0x080C.json")

    assert len(service.fields) == 1
    field = service.fields[0]
    assert field.name == "VertHeiRmdSts"
    assert field.getter is not None
    assert field.getter.element_id == 0x1001
    assert field.setter is None
    assert field.notifier is not None
    assert field.notifier.element_id == 0x9001
    assert field.notifier.eventgroup_id == 0x0001
