import subprocess
import sys

import pytest

import sms_sim
from sms_sim.__main__ import main


def test_version() -> None:
    assert sms_sim.__version__ == "0.1.0"


def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "sms_sim 0.1.0"


def test_runs_as_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sms_sim", "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "sms_sim 0.1.0"
