# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.11+ PySide SOME/IP manual test tool. Application code lives under `src/someip_gui_tool/`: `gui/` for the PySide UI, `domain/` for models and enums, `parsing/` for service JSON import, `codec/` for payload encoding, `adapters/` for SOME/IP backends, `tracing/` for trace export, and `project/` for saved state. Tests are in `tests/`. Sample service definitions are in `ADC40_SOC/*.json`. Packaging files live in `packaging/pyinstaller/`, and runtime scripts belong in `scripts/`.

## Build, Test, and Development Commands

Run all commands from the repository root inside the virtual environment. On PowerShell: `.venv\Scripts\Activate.ps1`.

- `python -m pip install -e ".[dev]"` installs the package in editable mode with test and packaging tools.
- `python -m pip install -e ".[dev,someipy]"` also installs the optional real SOME/IP backend.
- `python -m pytest` runs the full test suite using the repository pytest configuration.
- `python -m someip_gui_tool` starts the GUI from source.
- `someip-gui-tool` starts the installed console entry point.
- `python scripts/run_someipy_spike.py` runs the SOME/IP spike harness.
- `pyinstaller packaging/pyinstaller/someip-gui-tool.spec` builds the packaged GUI executable.

## Coding Style & Naming Conventions

Use 4-space indentation, type hints for public functions and data models, and small focused modules. Prefer `snake_case` for modules, functions, variables, and tests; use `PascalCase` for classes and Pydantic/Qt models. Keep imports explicit and grouped as standard library, third-party, then local package imports. Follow existing dataclass/Pydantic patterns before adding abstractions.

## Testing Guidelines

The project uses `pytest`, with `pytest-asyncio` and `pytest-qt` available for async and GUI coverage. Place tests in `tests/test_<feature>.py`, and name test functions `test_<expected_behavior>`. Add focused regression tests for parser, codec, adapter, tracing, and project-model changes. For GUI work, include smoke coverage similar to `tests/test_gui_smoke.py` when behavior is user-visible.

## Commit & Pull Request Guidelines

Git history uses short Conventional Commit-style subjects, such as `feat: add minimal pyside service browser`, `fix: validate service registry duplicate ids`, and `chore: add pyinstaller packaging smoke spec`. Keep commits scoped and imperative. Pull requests should include a concise summary, tests run, linked issues or context, and screenshots or short recordings for visible GUI changes.

## Security & Configuration Tips

Do not commit virtual environments, build outputs, or local machine configuration. Treat `ADC40_SOC` JSON files as test fixtures: update them deliberately and mention fixture changes in the PR summary. Keep optional `someipy` integration isolated behind adapter boundaries so the mock backend remains usable for local tests.
