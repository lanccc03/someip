import json
import subprocess
from pathlib import Path

import pytest

from someip_gui_tool.adapters.someipy_daemon import SomeipydConfig, SomeipydProcess


class FakePopen:
    def __init__(self, args, cwd=None, stdout=None, stderr=None):
        self.args = args
        self.cwd = cwd
        self.stdout = stdout
        self.stderr = stderr
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

    def communicate(self):
        return b"", b""


class ExitedPopen(FakePopen):
    def __init__(self, args, cwd=None, stdout=None, stderr=None):
        super().__init__(args, cwd=cwd, stdout=stdout, stderr=stderr)
        self.returncode = 2
        stderr.write(b"daemon bind failed")
        stderr.flush()


class TimeoutPopen(FakePopen):
    def wait(self, timeout=None):
        if self.killed:
            return self.returncode
        raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)


class KillTimeoutPopen(FakePopen):
    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)


def test_config_writes_someipyd_json(tmp_path):
    config = SomeipydConfig(
        interface="127.0.0.1",
        sd_address="239.192.255.251",
        sd_port=30490,
        tcp_host="127.0.0.2",
        tcp_port=30501,
    )

    path = config.write(tmp_path)

    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert '"interface": "127.0.0.1"' in text
    assert '"sd_address": "239.192.255.251"' in text
    assert '"sd_port": 30490' in text
    assert payload["log_level"] == "DEBUG"
    assert payload["use_tcp"] is True
    assert payload["tcp_host"] == "127.0.0.2"
    assert payload["tcp_port"] == 30501
    assert "log_path" not in payload


def test_config_writes_optional_log_path(tmp_path):
    config = SomeipydConfig(interface="127.0.0.1", log_path="someipyd.log")

    path = config.write(tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["log_path"] == "someipyd.log"


def test_config_client_config_matches_daemon_tcp_config():
    config = SomeipydConfig(interface="127.0.0.1", use_tcp=True, tcp_host="127.0.0.2", tcp_port=30501)

    assert config.client_config() == {
        "use_tcp": True,
        "tcp_host": "127.0.0.2",
        "tcp_port": 30501,
    }


def test_process_start_uses_someipyd_config(monkeypatch, tmp_path):
    created = []
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda args, cwd=None, stdout=None, stderr=None: created.append(
            FakePopen(args, cwd=cwd, stdout=stdout, stderr=stderr)
        )
        or created[-1],
    )

    process = SomeipydProcess.start(
        config=SomeipydConfig(interface="127.0.0.1"),
        work_dir=tmp_path,
        startup_timeout_s=0,
    )

    assert process.process.args[0] == "C:/tools/someipyd.exe"
    assert "--config" in process.process.args
    assert Path(process.process.args[-1]).exists()
    assert process.process.cwd == str(tmp_path)
    assert process.process.stdout != subprocess.PIPE
    assert process.process.stderr != subprocess.PIPE
    assert process.stdout_log_path == tmp_path / "someipyd-stdout.log"
    assert process.stderr_log_path == tmp_path / "someipyd-stderr.log"
    assert process.stdout_log_path.exists()
    assert process.stderr_log_path.exists()
    process.stop()
    assert process.process.terminated is True
    assert process.stdout_log_path.exists()
    assert process.stderr_log_path.exists()


def test_process_start_fails_when_daemon_exits_immediately(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda args, cwd=None, stdout=None, stderr=None: ExitedPopen(args, cwd=cwd, stdout=stdout, stderr=stderr),
    )

    with pytest.raises(RuntimeError, match="daemon exited"):
        SomeipydProcess.start(
            config=SomeipydConfig(interface="127.0.0.1"),
            work_dir=tmp_path,
            startup_timeout_s=0,
        )


def test_process_start_failure_includes_daemon_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda args, cwd=None, stdout=None, stderr=None: ExitedPopen(args, cwd=cwd, stdout=stdout, stderr=stderr),
    )

    with pytest.raises(RuntimeError, match="daemon bind failed"):
        SomeipydProcess.start(
            config=SomeipydConfig(interface="127.0.0.1"),
            work_dir=tmp_path,
            startup_timeout_s=0,
        )


def test_process_stop_closes_log_handles(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: "C:/tools/someipyd.exe")
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda args, cwd=None, stdout=None, stderr=None: FakePopen(args, cwd=cwd, stdout=stdout, stderr=stderr),
    )
    process = SomeipydProcess.start(
        config=SomeipydConfig(interface="127.0.0.1"),
        work_dir=tmp_path,
        startup_timeout_s=0,
    )

    process.stop()

    assert process.stdout_log.closed is True
    assert process.stderr_log.closed is True


def test_process_stop_kills_when_terminate_times_out(tmp_path):
    config_path = tmp_path / "someipyd-config.json"
    config_path.write_text("{}", encoding="utf-8")
    popen = TimeoutPopen(["someipyd"])
    process = SomeipydProcess(process=popen, config_path=config_path)

    process.stop()

    assert popen.terminated is True
    assert popen.killed is True
    assert not config_path.exists()


def test_process_stop_removes_config_when_process_already_exited(tmp_path):
    config_path = tmp_path / "someipyd-config.json"
    config_path.write_text("{}", encoding="utf-8")
    popen = FakePopen(["someipyd"])
    popen.returncode = 0
    process = SomeipydProcess(process=popen, config_path=config_path)

    process.stop()

    assert not config_path.exists()


def test_process_stop_removes_config_when_kill_wait_times_out(tmp_path):
    config_path = tmp_path / "someipyd-config.json"
    config_path.write_text("{}", encoding="utf-8")
    popen = KillTimeoutPopen(["someipyd"])
    process = SomeipydProcess(process=popen, config_path=config_path)

    process.stop()

    assert popen.terminated is True
    assert popen.killed is True
    assert not config_path.exists()


def test_process_start_fails_when_command_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda command: None)

    with pytest.raises(RuntimeError, match="someipyd command not found"):
        SomeipydProcess.start(config=SomeipydConfig(interface="127.0.0.1"), work_dir=tmp_path)
