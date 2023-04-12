from typing import TYPE_CHECKING
import pytest


from uoft_scripts import config

if TYPE_CHECKING:
    from .. import MockedUtil
    from pytest_mock import MockerFixture


@pytest.fixture()
def mock_config(mocker: "MockerFixture", mock_util: "MockedUtil"):

    mocker.patch.object(config, "util", mock_util)

    return config
