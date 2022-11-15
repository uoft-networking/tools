from uoft_core import BaseSettings, Field, chomptxt
from pydantic.types import SecretStr


class Settings(BaseSettings):
    """Settings for the snipeit application."""

    api_bearer_key: SecretStr = Field(
        description=chomptxt(
            """
            Please enter your API key. if you don't have one, a new API key can be generated for your account. 
            Log in to Snipe-IT, click on your account on the top-right of the screen, go to 'Manage API Keys', 
            and click 'Create New Token' to generate a new API key.
            """,
        )
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

    class Config(BaseSettings.Config):
        app_name = "snipeit"


def settings() -> Settings:
    return Settings.from_cache()  # pylint: disable=protected-access
