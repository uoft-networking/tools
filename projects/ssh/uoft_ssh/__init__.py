from importlib.metadata import version
from uoft_core import BaseSettings, Field
from uoft_core.types import BaseModel, SecretStr

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore


class Credentials(BaseModel):
    """Credentials for a device."""
    username: str
    password: SecretStr


class Settings(BaseSettings):
    """Settings for the ssh application."""
    enable_secret: SecretStr = Field(description="Password used to enter the enable mode of a device.")
    admin: Credentials = Field(description="Credentials for the admin user.")
    personal: Credentials = Field(description="Your personal credentials.")
    other: dict[str, SecretStr] = Field(description="Other, optional credentials.")


    class Config(BaseSettings.Config):
        app_name = "ssh"
