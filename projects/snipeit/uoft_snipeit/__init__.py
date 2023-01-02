from uoft_core import BaseSettings, Field, chomptxt
from pydantic.types import SecretStr


class Settings(BaseSettings):
    """Settings for the snipeit application."""

    api_bearer_key: SecretStr = Field(
        description="User API bearer key used with SnipeIT instance.",
    )
    snipeit_hostname: str = Field(
        description="Hostname of SnipeIT instance.",
    )

    class Config(BaseSettings.Config):
        app_name = "snipeit"


def settings() -> Settings:
    return Settings.from_cache()  # pylint: disable=protected-access
