from typing import TYPE_CHECKING

from uoft_scripts import Config

if TYPE_CHECKING:
    from .. import MockedUtil

    class MockedConfig(Config):
        util: MockedUtil
