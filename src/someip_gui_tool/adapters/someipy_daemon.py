from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SomeipydConfig:
    interface: str
    sd_address: str = "239.192.255.251"
    sd_port: int = 30490
    log_level: str = "DEBUG"

    def as_dict(self) -> dict[str, object]:
        return {
            "interface": self.interface,
            "sd_address": self.sd_address,
            "sd_port": self.sd_port,
            "log_level": self.log_level,
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

    @classmethod
    def start(cls, config: SomeipydConfig, work_dir: Path) -> SomeipydProcess:
        command = shutil.which("someipyd")
        if command is None:
            raise RuntimeError("someipyd command not found. Install with: python -m pip install -e .[someipy]")

        config_path = config.write(work_dir)
        process = subprocess.Popen([command, "--config", str(config_path)], cwd=str(work_dir))
        return cls(process=process, config_path=config_path)

    def stop(self) -> None:
        if self.process.poll() is not None:
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
