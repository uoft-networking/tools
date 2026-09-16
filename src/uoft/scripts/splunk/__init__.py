from uoft.core import BaseSettings, SecretStr


class Settings(BaseSettings):
    host: str
    token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "splunk"

    def get_api_connection(self):
        from uoft.scripts.splunk.lib import API

        return API(host=self.host, token=self.token, verify=False)
