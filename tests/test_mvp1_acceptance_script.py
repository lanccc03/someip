from __future__ import annotations

from pathlib import Path

import scripts.run_mvp1_acceptance as acceptance


def test_acceptance_runner_runs_required_default_commands(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        calls.append(list(command))
        assert cwd == Path.cwd()
        assert check is True

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    assert acceptance.main(["--skip-real", "--skip-package"]) == 0

    assert calls[0][-3:] == ["-m", "pytest", "-q"]
    assert calls[1][-2:] == ["--mode", "dry-run"]
    assert all("pyinstaller" not in call for command in calls for call in command)


def test_acceptance_runner_can_include_real_and_package(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, cwd, check):
        calls.append(list(command))

    monkeypatch.setattr(acceptance.subprocess, "run", fake_run)

    assert acceptance.main([]) == 0

    assert any("--start-daemon" in command for command in calls)
    assert any("PyInstaller" in command for command in calls)
    assert any("--smoke-exit" in command for command in calls)
