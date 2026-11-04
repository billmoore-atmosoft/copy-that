"""Run native GUI checks in a fresh Tcl process, isolated from hook tests."""
from pathlib import Path
import subprocess
import sys


def test_theme_ui_in_isolated_process():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/theme_scenarios.py", "-q",
         "--basetemp=.test-temp/theme-ui"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
