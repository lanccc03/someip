from __future__ import annotations

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
