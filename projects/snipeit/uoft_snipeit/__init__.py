from uoft_core import BaseSettings, Field
from pydantic.types import SecretStr


class Settings(BaseSettings):
    """Settings for the snipeit application."""

    api_bearer_key: SecretStr = Field(
        description="API bearer key used to authenticate to the SnipeIT API.",
    )
    snipeit_hostname: str = Field(
        description="Hostname of SnipeIT instance.",
    )

    def headers(self):
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_bearer_key.get_secret_value()}",
            "content-type": "application/json",
        }

    class Config(BaseSettings.Config):
        app_name = "snipeit"


def settings() -> Settings:
    return Settings.from_cache()  # pylint: disable=protected-access


def headers() -> Settings:
    return headers()
