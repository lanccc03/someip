from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run MVP-1 acceptance checks.")
    parser.add_argument("--skip-real", action="store_true", help="Skip real someipy loopback.")
    parser.add_argument("--skip-package", action="store_true", help="Skip PyInstaller package smoke.")
    args = parser.parse_args(argv)

    python = sys.executable
    commands = [
        [python, "-m", "pytest", "-q"],
        [python, "scripts/run_protocol_spike.py", "--mode", "dry-run"],
    ]
    if not args.skip_real:
        commands.append(
            [
                python,
                "scripts/run_protocol_spike.py",
                "--mode",
                "real",
                "--start-daemon",
            ]
        )
    if not args.skip_package:
        commands.extend(
            [
                [python, "-m", "PyInstaller", "packaging/pyinstaller/someip-gui-tool.spec"],
                [str(REPO_ROOT / "dist" / "someip-gui-tool.exe"), "--smoke-exit"],
            ]
        )

    for command in commands:
        subprocess.run(command, cwd=REPO_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
