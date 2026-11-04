import re
import version


def test_label_names_the_version_and_a_dev_checkout():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.VERSION)
    assert version.label().startswith(f"{version.VERSION} dev")


def test_build_script_and_installer_read_the_one_version():
    from pathlib import Path
    root = Path(version.__file__).parent
    assert '"0.' not in (root / "scripts/build_windows.py").read_text(encoding="utf-8")
