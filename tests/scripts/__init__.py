from typing import TYPE_CHECKING

from utsc.scripts import Config

if TYPE_CHECKING:
    from .. import MockedUtil

    class MockedConfig(Config):
        util: MockedUtil
