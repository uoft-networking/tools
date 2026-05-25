from typing import TYPE_CHECKING
import pytest

from . import CapturedOutput

from uoft_switchconfig import config

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input

if TYPE_CHECKING:
    from uoft_core.tests import MockedUtil
    from pytest_mock import MockerFixture


@pytest.fixture()
def mock_config(mocker: "MockerFixture", mock_util: "MockedUtil"):
    mocker.patch.object(config, "util", mock_util)

    return config


@pytest.fixture(scope="function")
def mock_pt_app():
    pipe_output = CapturedOutput()
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=pipe_output) as app:
            yield app


# endregion
