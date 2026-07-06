from importlib.metadata import version
from typing import Optional

from uoft.core import BaseSettings, Field, txt
from uoft.core.types import SecretStr


class Settings(BaseSettings):
    """Settings for the paloalto application."""

    url: str = Field(
        title="URL",
        description="The base URL of the Palo Alto REST API server. (ex. https://paloalto.example.com)",
    )
    username: str = Field(
        title="Username",
        description="The username to authenticate with the Palo Alto REST API server.",
    )
    password: SecretStr = Field(
        title="Password",
        description="The password to authenticate with the Palo Alto REST API server.",
    )

    api_key: Optional[SecretStr] = Field(
        title="API Key",
        description="API key to authenticate with the Palo Alto XML API server. "
        "Leave blank if you want to generate one later",
    )

    panorama: bool = Field(
        title="Panorama",
        description="Whether the REST API we're connecting to is a Panorama instance or a Palo Alto device",
        default=True,
    )

    device_group: Optional[str] = Field(
        title="Device Group",
        description="The device group to use when managing objects. "
        "If not provided, objects will be placed in the 'shared' device group.",
        default=None,
    )

    create_missing_tags: bool = Field(
        title="Create Missing Tags",
        description="If enabled, missing tags assigned to objects will be created automatically.",
        default=False,
    )

    verify: bool = Field(
        title="SSL Verification",
        description="Whether to verify SSL certificates when connecting to the Palo Alto REST API server.",
        default=True,
    )

    class Config(BaseSettings.Config):
        app_name = "paloalto"

    def get_api_connection(self):
        from .api import API

        return API(
            self.url,
            self.username,
            self.password,
            api_key=self.api_key,
            panorama=self.panorama,
            device_group=self.device_group,
            create_missing_tags=self.create_missing_tags,
            verify=self.verify,
        )
