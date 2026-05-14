from someip_gui_tool.spike.result import SpikeStatus
from someip_gui_tool.spike.runner import ProtocolSpikeRunner
from someip_gui_tool.spike.scenarios import ScenarioKind, build_scenarios


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
