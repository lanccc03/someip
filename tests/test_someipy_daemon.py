import json
import subprocess
from pathlib import Path

import pytest

from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess


class FakePopen:
    def __init__(self, args, cwd=None):
        self.args = args
        self.cwd = cwd
        self.terminated = False
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class TimeoutPopen(FakePopen):
    def wait(self, timeout=None):
        if self.killed:
            return self.returncode
        raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)


def test_config_writes_someipyd_json(tmp_path):
    config = SomeipydConfig(interface="127.0.0.1", sd_address="239.192.255.251", sd_port=30490)

    path = config.write(tmp_path)

    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert '"interface": "127.0.0.1"' in text
    assert '"sd_address": "239.192.255.251"' in text
    assert '"sd_port": 30490' in text
    assert payload["log_level"] == "DEBUG"


def test_process_start_uses_someipyd_config(monkeypatch, tmp_path):
    created = []
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr("subprocess.Popen", lambda args, cwd=None: created.append(FakePopen(args, cwd)) or created[-1])

    process = SomeipydProcess.start(
        config=SomeipydConfig(interface="127.0.0.1"),
        work_dir=tmp_path,
    )

    assert process.process.args[0] == "C:/tools/someipyd.exe"
    assert "--config" in process.process.args
    assert Path(process.process.args[-1]).exists()
    assert process.process.cwd == str(tmp_path)
    process.stop()
    assert process.process.terminated is True


def test_process_stop_kills_when_terminate_times_out():
    popen = TimeoutPopen(["someipyd"])
    process = SomeipydProcess(process=popen, config_path=Path("someipyd-config.json"))

    process.stop()

    assert popen.terminated is True
    assert popen.killed is True


def test_process_start_fails_when_command_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: None)

    with pytest.raises(RuntimeError, match="someipyd command not found"):
        SomeipydProcess.start(config=SomeipydConfig(interface="127.0.0.1"), work_dir=tmp_path)
