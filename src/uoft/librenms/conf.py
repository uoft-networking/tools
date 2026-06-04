from uoft.core import BaseSettings
from pydantic.v1 import AnyHttpUrl, SecretStr
from .api import LibreNMSRESTAPI


class Settings(BaseSettings):
    url: AnyHttpUrl
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "librenms"

    def api_connection(self):
        return LibreNMSRESTAPI(self.url, self.token.get_secret_value())
