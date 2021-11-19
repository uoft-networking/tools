from typing import TYPE_CHECKING
import pytest

from . import CapturedOutput

from utsc.switchconfig import config

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input

if TYPE_CHECKING:
    from .. import MockedUtil
    from pytest_mock import MockerFixture


@pytest.fixture()
def mock_config(mocker: "MockerFixture", mock_util: "MockedUtil"):
    from . import templates  # noqa

    mocker.patch.object(config, "util", mock_util)
    mocker.patch("utsc.switchconfig.Config.templates", templates)

    return config


@pytest.fixture(scope="function")
def mock_pt_app():
    pipe_input = create_pipe_input()
    pipe_output = CapturedOutput()
    try:
        with create_app_session(input=pipe_input, output=pipe_output) as app:
            yield app
    finally:
        pipe_input.close()


# endregion

# region failed interactive fixture experiment
# def pytest_addoption(parser):
#     parser.addoption(
#         "--interactive", action="store_true", default=False, help="run interactive tests"
#     )

# @pytest.fixture()
# def interactive(request, capfd: 'CaptureFixture'):
#     if request.config.getoption("--interactive") or os.getenv("VSCODE_DEBUGGER"):
#         # here we reach directly into capsys._capture,
#         # because the capsys.disabled context manager
#         # does not suspend capturing of stdin.
#         capmanager: 'CaptureManager' = capfd.request.config.pluginmanager.getplugin("capturemanager")
#         capmanager.suspend(in_=True)
#         assert capfd._capture # noqa
#         capfd._capture.suspend_capturing(in_=True) # noqa
#         yield
#         capmanager.resume()
#         capfd._capture.resume_capturing() # noqa
#     else:
#         pytest.skip("This test can only be run with the --interactive option")


# def pytest_collection_modifyitems(config, items):
#     if config.getoption("--interactive"):
#         # --interactive given in cli: do not skip interactive tests
#         return
#     skip_interactive = pytest.mark.skip(reason="need --interactive option to run")
#     for item in items:
#         if "interactive" in item.keywords and not os.getenv("VSCODE_DEBUGGER"):
#             item.add_marker(skip_interactive)
# endregion
