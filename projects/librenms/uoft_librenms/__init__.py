from uoft_core import BaseSettings
from pydantic import AnyHttpUrl, SecretStr
from .api import LibreNMSRESTAPIClient


class Settings(BaseSettings):
    url: AnyHttpUrl
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "librenms"

    def api_connection(self):
        return LibreNMSRESTAPIClient(self.url, self.token.get_secret_value())
