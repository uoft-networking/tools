# pylint: disable=unused-argument
from typing import TYPE_CHECKING

from utsc.core import txt
from utsc.scripts import bluecat

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from . import MockedConfig


@pytest.mark.skip("need to figure out how to run bluecat test instance")
def test_bluecat(mock_config: "MockedConfig", monkeypatch: "MonkeyPatch") -> None:
    """Test bluecat."""
    mock_config.util.mock_folders.user_config.toml_file.write_text(
        txt(
            """
        [bluecat]
        url = "https://some-bluecat-instance"
        username = "username"
        password_cmd = "echo 'some password'"
        """
        )
    )
    bluecat.collect()
