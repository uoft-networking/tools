from uoft_core import BaseSettings
from pydantic import AnyHttpUrl, SecretStr


class Settings(BaseSettings):
    url: AnyHttpUrl
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "librenms"

    def api_connection(self):
        from .api import LibreNMSRESTAPIClient
        return LibreNMSRESTAPIClient(self.url, self.token.get_secret_value())
