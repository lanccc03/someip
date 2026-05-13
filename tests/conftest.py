from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def adc40_soc_dir(repo_root: Path) -> Path:
    return repo_root / "ADC40_SOC"
