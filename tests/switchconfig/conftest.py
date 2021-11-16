from typing import TYPE_CHECKING
import pytest

from utsc.switchconfig import config, Config

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

if TYPE_CHECKING:
    from .. import MockUtilFolders, MockFolders
    from pytest_mock import MockerFixture
    from prompt_toolkit.application.current import AppSession
    from prompt_toolkit.input.base import PipeInput
    class MockPTApp(AppSession):
        input: PipeInput


class MockedConfig(Config):
    mock_folders: "MockFolders"


@pytest.fixture()
def mock_config(mocker: "MockerFixture", mock_folders: "MockUtilFolders"):
    util, folders = mock_folders
    from . import templates # noqa

    mocker.patch.object(config, "util", util)
    mocker.patch("utsc.switchconfig.Config.templates", templates)
    config.mock_folders = folders # type: ignore

    yield folders

    del config.mock_folders # type: ignore

# region interactive fixture
class CapturedOutput(DummyOutput):
    "Emulate an stdout object."
    def encoding(self):
        return "utf-8"

    def __init__(self):
        self._data = []

    def write(self, data):
        self._data.append(data)

    @property
    def data(self):
        return "".join(self._data)

    def isatty(self):
        return True

    def fileno(self):
        # File descriptor is not used for printing formatted text.
        # (It is only needed for getting the terminal size.)
        return -1


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