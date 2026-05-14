from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class SomeipydConfig:
    interface: str
    sd_address: str = "239.192.255.251"
    sd_port: int = 30490
    log_level: str = "DEBUG"
    use_tcp: bool = True
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 30500
    log_path: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "interface": self.interface,
            "sd_address": self.sd_address,
            "sd_port": self.sd_port,
            "log_level": self.log_level,
            "use_tcp": self.use_tcp,
            "tcp_host": self.tcp_host,
            "tcp_port": self.tcp_port,
        }
        if self.log_path is not None:
            payload["log_path"] = self.log_path
        return payload

    def client_config(self) -> dict[str, object]:
        return {
            "use_tcp": self.use_tcp,
            "tcp_host": self.tcp_host,
            "tcp_port": self.tcp_port,
        }

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "someipyd-config.json"
        path.write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")
        return path


@dataclass
class SomeipydProcess:
    process: subprocess.Popen
    config_path: Path
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None
    stdout_log: BinaryIO | None = None
    stderr_log: BinaryIO | None = None

    @classmethod
    def start(cls, config: SomeipydConfig, work_dir: Path, startup_timeout_s: float = 0.2) -> SomeipydProcess:
        command = shutil.which("someipyd")
        if command is None:
            raise RuntimeError("someipyd command not found. Install with: python -m pip install -e .[someipy]")

        config_path = config.write(work_dir)
        stdout_log_path = work_dir / "someipyd-stdout.log"
        stderr_log_path = work_dir / "someipyd-stderr.log"
        stdout_log = stdout_log_path.open("wb")
        stderr_log = stderr_log_path.open("wb")
        try:
            process = subprocess.Popen(
                [command, "--config", str(config_path)],
                cwd=str(work_dir),
                stdout=stdout_log,
                stderr=stderr_log,
            )
            if startup_timeout_s > 0:
                time.sleep(startup_timeout_s)
            if process.poll() is not None:
                detail = _format_log_output(
                    stdout_log_path=stdout_log_path,
                    stderr_log_path=stderr_log_path,
                    stdout_log=stdout_log,
                    stderr_log=stderr_log,
                )
                raise RuntimeError(f"someipyd daemon exited during startup with code {process.returncode}.{detail}")
        except Exception:
            _close_log(stdout_log)
            _close_log(stderr_log)
            config_path.unlink(missing_ok=True)
            raise
        return cls(
            process=process,
            config_path=config_path,
            stdout_log_path=stdout_log_path,
            stderr_log_path=stderr_log_path,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )

    def stop(self) -> None:
        try:
            if self.process.poll() is not None:
                return

            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            _close_log(self.stdout_log)
            _close_log(self.stderr_log)
            self.config_path.unlink(missing_ok=True)


def _format_log_output(
    *,
    stdout_log_path: Path,
    stderr_log_path: Path,
    stdout_log: BinaryIO,
    stderr_log: BinaryIO,
) -> str:
    _flush_log(stdout_log)
    _flush_log(stderr_log)
    parts = []
    stdout_text = _read_log_text(stdout_log_path).strip()
    stderr_text = _read_log_text(stderr_log_path).strip()
    if stdout_text:
        parts.append(f" stdout: {stdout_text}")
    if stderr_text:
        parts.append(f" stderr: {stderr_text}")
    return "".join(parts)


def _read_log_text(path: Path, max_chars: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


def _flush_log(log: BinaryIO) -> None:
    try:
        log.flush()
    except OSError:
        pass


def _close_log(log: BinaryIO | None) -> None:
    if log is None:
        return
    try:
        log.close()
    except OSError:
        pass
