from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def test_dry_run_text_output_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_protocol_spike.py",
            "--definition-root",
            "ADC40_SOC",
            "--mode",
            "dry-run",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "someipy-protocol-spike-dry-run" in result.stdout
    assert "PASS udp-ff-method" in result.stdout


def test_json_report_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "protocol-spike.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_protocol_spike.py",
            "--definition-root",
            "ADC40_SOC",
            "--mode",
            "dry-run",
            "--json-report",
            str(report_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["name"] == "someipy-protocol-spike-dry-run"
    assert payload["failed"] is False


def test_script_runs_with_local_src_bootstrap() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "scripts/run_protocol_spike.py",
            "--definition-root",
            "ADC40_SOC",
            "--mode",
            "dry-run",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "someipy-protocol-spike-dry-run" in result.stdout


def test_default_definition_root_resolves_from_script_repo(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_protocol_spike.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "someipy-protocol-spike-dry-run" in result.stdout


def test_real_mode_forwards_options_and_writes_failed_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "real-report.json"
    script_module = _load_protocol_spike_script()
    calls = []

    class FakeReport:
        failed = True

        def as_text(self):
            return "fake real report"

        def as_dict(self):
            return {"name": "fake-real", "failed": True}

    class FakeRunner:
        def __init__(self, definition_root):
            self.definition_root = definition_root

        def run_real(self, *, local_ip, base_port, start_daemon):
            calls.append(
                {
                    "definition_root": self.definition_root,
                    "local_ip": local_ip,
                    "base_port": base_port,
                    "start_daemon": start_daemon,
                }
            )
            return FakeReport()

    monkeypatch.setattr(script_module, "ProtocolSpikeRunner", FakeRunner)

    exit_code = script_module.main(
        [
            "--mode",
            "real",
            "--local-ip",
            "127.0.0.42",
            "--base-port",
            "32000",
            "--start-daemon",
            "--json-report",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert calls == [
        {
            "definition_root": Path(__file__).resolve().parents[1] / "ADC40_SOC",
            "local_ip": "127.0.0.42",
            "base_port": 32000,
            "start_daemon": True,
        }
    ]
    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "name": "fake-real",
        "failed": True,
    }


def _load_protocol_spike_script():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_protocol_spike.py"
    spec = importlib.util.spec_from_file_location("run_protocol_spike_under_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
