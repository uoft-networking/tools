from pathlib import Path
import pytest

from uoft_switchconfig import __version__

from uoft_core import toml


@pytest.mark.skip("needs more work")
def test_version():
    pyproject = toml.loads(
        Path("projects/switchconfig/pyproject.toml").read_text(encoding="utf-8")
    )
    expected_version = pyproject["tool"]["poetry"]["version"]
    assert __version__ == expected_version
