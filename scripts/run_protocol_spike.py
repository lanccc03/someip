from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from someip_gui_tool.spike.runner import ProtocolSpikeRunner


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SOME/IP protocol spike scenarios.")
    parser.add_argument("--definition-root", default="ADC40_SOC")
    parser.add_argument("--mode", choices=("dry-run", "real"), default="dry-run")
    parser.add_argument("--local-ip", default="127.0.0.1")
    parser.add_argument("--base-port", type=int, default=30500)
    parser.add_argument("--start-daemon", action="store_true")
    parser.add_argument("--json-report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    definition_root = _resolve_definition_root(Path(args.definition_root))
    runner = ProtocolSpikeRunner(definition_root)
    if args.mode == "dry-run":
        report = runner.run_dry()
    else:
        report = runner.run_real(
            local_ip=args.local_ip,
            base_port=args.base_port,
            start_daemon=args.start_daemon,
        )

    print(report.as_text())
    if args.json_report:
        Path(args.json_report).write_text(
            json.dumps(report.as_dict(), indent=2),
            encoding="utf-8",
        )
    return 1 if report.failed else 0


def _resolve_definition_root(definition_root: Path) -> Path:
    if definition_root.is_absolute():
        return definition_root
    return REPO_ROOT / definition_root


if __name__ == "__main__":
    raise SystemExit(main())
