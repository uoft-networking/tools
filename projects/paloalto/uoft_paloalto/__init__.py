from importlib.metadata import version

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
__version__ = version(__package__) # type: ignore


class Settings(BaseSettings):
    """Settings for the paloalto application."""

    url: str = Field(
        title="URL",
        description="The base URL of the Palo Alto REST API server. (ex. https://paloalto.example.com)",
    )
    username: str = Field(
        title="Username",
        description="The username to authenticate with the Palo Alto REST API server.",
    )
    password: SecretStr = Field(
        title="Password",
        description="The password to authenticate with the Palo Alto REST API server.",
    )

    class Config(BaseSettings.Config):
        app_name = "paloalto"
    
    def get_api_connection(self):
        from .api import API
        return API(self.url, self.username, self.password.get_secret_value())
