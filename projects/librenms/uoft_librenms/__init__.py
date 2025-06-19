from importlib.metadata import version

from uoft_core import BaseSettings
from pydantic.v1 import AnyHttpUrl, SecretStr
from .api import LibreNMSRESTAPI

# All of our projects are distributed as packages, so we can use the importlib.metadata
# module to get the version of the package.
assert __package__
__version__ = version(__package__)  # type: ignore


class Settings(BaseSettings):
    url: AnyHttpUrl
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "librenms"

    def api_connection(self):
        return LibreNMSRESTAPI(self.url, self.token.get_secret_value())
