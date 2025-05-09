from importlib.metadata import version

from uoft_core import BaseSettings, Field
from pydantic.types import SecretStr

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore


class Settings(BaseSettings):
    """Settings for the phpipam application."""

    hostname: str = Field(
        description="Hostname of phpIPAM instance.",
    )
    username: str = Field(
        description="Username for phpIPAM instance.",
    )
    password: SecretStr = Field(
        description="Password for phpIPAM instance.",
    )
    app_id: str = Field(
        description="App id for API access.",
    )

    class Config(BaseSettings.Config):
        app_name = "phpipam"


def settings() -> Settings:
    return Settings.from_cache()  # pylint: disable=protected-access
