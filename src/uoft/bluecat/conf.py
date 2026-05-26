from uoft.core.logging import getLogger
from uoft.core import BaseSettings, Field, SecretStr

logger = getLogger(__name__)


class Settings(BaseSettings):
    """Settings for the bluecat application."""

    url: str = Field("https://localhost")
    username: str = "admin"
    password: SecretStr = SecretStr("")
    dhcp_only_network_ids: list[int] = Field(
        default_factory=set,
        description="Network IDs that contain only DHCP-assigned addresses",
    )
    configuration: str | None = Field("UTSCProduction", description="BlueCat configuration name")

    class Config(BaseSettings.Config):
        app_name = "bluecat"

    def get_api_connection(self, configuration: str | None = None):
        from .api import API

        configuration = configuration or self.configuration

        return API(self.url, self.username, self.password.get_secret_value(), configuration=configuration)


class STGSettings(Settings):
    class Config(BaseSettings.Config):  # pyright: ignore[reportIncompatibleVariableOverride]
        app_name = "bluecat-stg"
