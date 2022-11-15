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
    default_model_id: int = Field(
        default=138,
        description="Default model ID to use when creating assets.",
    )
    default_assigned_location_id: int = Field(
        default=150,
        description="Default assigned location to use when checking out assets.",
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
