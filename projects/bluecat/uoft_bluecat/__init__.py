from importlib.metadata import version

from uoft_core.logging import getLogger
from uoft_core import BaseSettings, Field, SecretStr

logger = getLogger(__name__)

# All of our projects are distributed as packages, so we can use the importlib.metadata
# module to get the version of the package.
assert __package__
__version__ = version(__package__)


class Settings(BaseSettings):
    """Settings for the bluecat application."""

    url: str = Field("https://localhost")
    username: str = "admin"
    password: SecretStr = SecretStr("")
    dhcp_only_network_ids: list[int] = Field(
        default_factory=set,
        description="Network IDs that contain only DHCP-assigned addresses",
    )

    class Config(BaseSettings.Config):
        app_name = "bluecat"

    def get_api_connection(self):
        from .api import API

        return API(self.url, self.username, self.password.get_secret_value())


class STGSettings(Settings):
    class Config(BaseSettings.Config):  # pyright: ignore[reportIncompatibleVariableOverride]
        app_name = "bluecat-stg"
