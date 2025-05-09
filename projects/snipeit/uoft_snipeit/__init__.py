from importlib.metadata import version

from uoft_core import BaseSettings, Field
from pydantic.types import SecretStr

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore


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
