from typing import TYPE_CHECKING

from utsc.switchconfig import Config

from prompt_toolkit.output import DummyOutput

if TYPE_CHECKING:
    from .. import MockedUtil
    from prompt_toolkit.application.current import AppSession
    from prompt_toolkit.input.base import PipeInput

    class MockPTApp(AppSession):
        input: PipeInput

    class MockedConfig(Config):
        util: MockedUtil




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