from uoft.core import BaseSettings, Field
from uoft.core.types import BaseModel, SecretStr


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
    terminal_server: Credentials = Field(description="Credentials for the tripplite terminal servers.")
    airconsole: Credentials = Field(description="Credentials for the Airconsole terminal servers.")

    class Config(BaseSettings.Config):
        app_name = "ssh"
