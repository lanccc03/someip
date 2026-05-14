from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from someip_gui_tool.adapters.someipy_spike import describe_spike_plan


def test_describe_spike_plan_includes_key_items() -> None:
    plan = describe_spike_plan()

    assert "Start or connect to someipyd" in plan
    assert "Run UDP FF method with 0x080D SecondStartCtrl" in plan
    assert "Run TCP method with 0x0F01 AudioRecPopupReq" in plan
    assert "Run UDP cycle event with 0x080E VehicleInfo" in plan
    assert "Run Field Getter/Notifier with 0x080C VertHeiRmdSts" in plan


def test_script_runs_from_repo_root_with_local_src_bootstrap() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-S", "scripts/run_someipy_spike.py"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode in {0, 2}
    assert "Spike checklist:" in result.stdout
