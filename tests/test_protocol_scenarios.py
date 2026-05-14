from dataclasses import replace

from someip_gui_tool.domain.models import FieldDefinition
from someip_gui_tool.spike.result import SpikeStatus
from someip_gui_tool.spike.runner import ProtocolSpikeRunner
from someip_gui_tool.spike.scenarios import ProtocolScenario, ScenarioKind, build_scenarios


def test_builds_required_scenarios(adc40_soc_dir):
    scenarios = build_scenarios(adc40_soc_dir)

    assert [scenario.kind for scenario in scenarios] == [
        ScenarioKind.UDP_FF_METHOD,
        ScenarioKind.TCP_METHOD,
        ScenarioKind.UDP_EVENT,
        ScenarioKind.TCP_EVENT,
        ScenarioKind.FIELD_GETTER_NOTIFIER,
    ]
    assert [scenario.service.service_id for scenario in scenarios] == [
        0x080D,
        0x0F01,
        0x080E,
        0x080A,
        0x080C,
    ]
    assert scenarios[0].method is not None
    assert scenarios[0].method.name == "SecondStartCtrl"
    assert scenarios[0].payload_values == {"SecondStartCtrlCmd": 1}
    assert scenarios[1].method is not None
    assert scenarios[1].method.name == "AudioRecPopupReq"
    assert scenarios[1].payload_values == {"AudioRecPopup": 1}
    assert scenarios[2].event is not None
    assert scenarios[2].event.name == "VehicleInfo"
    assert scenarios[2].payload_values == {
        "VehicleInfo": {"VehicleSpeed": 12.5, "Odometer": 99.25}
    }
    assert scenarios[3].event is not None
    assert scenarios[3].event.name == "IntellgntSwtDecoupSts"
    assert scenarios[3].payload_values == {"IntellgntSwtDecoupSts": [1, 2, 3]}
    assert scenarios[4].field is not None
    assert scenarios[4].field.name == "VertHeiRmdSts"
    assert scenarios[4].field.getter is not None
    assert scenarios[4].field.getter.element_id == 0x1001
    assert scenarios[4].field.notifier is not None
    assert scenarios[4].field.notifier.element_id == 0x9001
    assert scenarios[4].payload_values == {"VertHeiRmdSts": 1}


def test_dry_run_validates_payloads_and_services(adc40_soc_dir):
    report = ProtocolSpikeRunner(adc40_soc_dir).run_dry()

    assert report.name == "someipy-protocol-spike-dry-run"
    assert report.failed is False
    assert [step.status for step in report.steps] == [SpikeStatus.PASS] * 5
    assert [step.name for step in report.steps] == [
        "udp-ff-method",
        "tcp-method",
        "udp-event",
        "tcp-event",
        "field-getter-notifier",
    ]
    assert [step.data["service_id"] for step in report.steps] == [
        "0x080D",
        "0x0F01",
        "0x080E",
        "0x080A",
        "0x080C",
    ]
    assert all(step.data["payload_hex"] for step in report.steps)

    assert report.steps[0].data == {
        "service_id": "0x080D",
        "payload_hex": "01",
        "transport": "UDP",
        "method_id": "0x0001",
        "rr_ff": "FF",
    }
    assert report.steps[1].data == {
        "service_id": "0x0F01",
        "payload_hex": "0000000000000001",
        "transport": "TCP",
        "method_id": "0x0001",
        "rr_ff": "FF",
    }
    assert report.steps[2].data == {
        "service_id": "0x080E",
        "payload_hex": "4148000042c68000",
        "transport": "UDP",
        "event_id": "0x8001",
        "send_strategy": "Cycle",
        "eventgroup_id": "0x0001",
    }
    assert report.steps[3].data == {
        "service_id": "0x080A",
        "payload_hex": "010203",
        "transport": "TCP",
        "event_id": "0x8001",
        "send_strategy": "Trigger",
        "eventgroup_id": "0x0001",
    }
    assert report.steps[4].data == {
        "service_id": "0x080C",
        "payload_hex": "01",
        "transport": "TCP",
        "getter_id": "0x1001",
        "notifier_id": "0x9001",
        "notifier_eventgroup_id": "0x0001",
        "getter_transport": "TCP",
        "notifier_transport": "TCP",
    }


def test_dry_run_fails_when_field_getter_is_missing(adc40_soc_dir):
    scenario = _field_scenario(adc40_soc_dir)
    assert scenario.field is not None
    scenario = replace(
        scenario,
        field=FieldDefinition(
            name=scenario.field.name,
            getter=None,
            setter=scenario.field.setter,
            notifier=scenario.field.notifier,
        ),
    )

    step = ProtocolSpikeRunner(adc40_soc_dir)._dry_step(scenario)

    assert step.status is SpikeStatus.FAIL
    assert "getter" in step.detail


def test_dry_run_fails_when_field_notifier_id_is_wrong(adc40_soc_dir):
    scenario = _field_scenario(adc40_soc_dir)
    assert scenario.field is not None
    assert scenario.field.notifier is not None
    scenario = replace(
        scenario,
        field=FieldDefinition(
            name=scenario.field.name,
            getter=scenario.field.getter,
            setter=scenario.field.setter,
            notifier=replace(scenario.field.notifier, element_id=0x9002),
        ),
    )

    step = ProtocolSpikeRunner(adc40_soc_dir)._dry_step(scenario)

    assert step.status is SpikeStatus.FAIL
    assert "notifier" in step.detail


def _field_scenario(adc40_soc_dir) -> ProtocolScenario:
    return build_scenarios(adc40_soc_dir)[4]
