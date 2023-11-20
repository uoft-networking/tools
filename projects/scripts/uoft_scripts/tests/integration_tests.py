# pylint: disable=unused-argument
from typing import TYPE_CHECKING

from uoft_core import txt
from uoft_scripts import bluecat

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

    from uoft_scripts import Config
    from uoft_core.tests import MockedUtil

    class MockedConfig(Config):
        util: MockedUtil


@pytest.mark.skip("need to figure out how to run bluecat test instance")
def test_bluecat(mock_config: "MockedConfig", monkeypatch: "MonkeyPatch") -> None:
    """Test bluecat."""
    with pytest.raises(ValueError):
        int('hello')
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
