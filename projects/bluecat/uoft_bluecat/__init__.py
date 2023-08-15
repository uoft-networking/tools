from typing import Literal

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr
from uoft_core._vendor.bluecat_libraries.address_manager.api import Client
from uoft_core._vendor.bluecat_libraries.address_manager.constants import (
    IPAssignmentActionValues,
    ObjectType,
    OptionType,
)


class API:
    """This class is a wrapper around the bluecat_libraries.address_manager.api.Client class"""

    def __init__(self, url, username, password) -> None:
        self.client = Client(url)
        self.client.login(username, password)

    def get_configuration(self, name: str | None = None):
        """Get a configuration by name, or the first available configuration if no name is provided"""
        if name:
            return self.client.get_entity_by_name(0, name, ObjectType.CONFIGURATION)
        return self.client.get_entities(0, ObjectType.CONFIGURATION)[0]

    def get_entities(self, parent_id, typ, start=0):
        page_size = 100
        entities = self.client.get_entities(
            parent_id, typ, start=start, count=page_size
        )
        yield from entities
        if len(entities) == page_size:
            yield from self.get_entities(parent_id, typ, start=start + page_size)

    def get_ipv4_address(
        self,
        address: str,
        configuration_id: int | None = None,
    ):

        if not configuration_id:
            configuration_id = self.get_configuration()["id"]
        assert configuration_id is not None

        return self.client.get_entity_by_cidr(
            cidr=f"{address}/32", type=ObjectType.IP4_ADDRESS, parent_id=configuration_id
        )

    def assign_ipv4_address(
        self,
        address: str,
        mac_address: str,
        hostname: str | None = None,
        address_type: Literal["static", "reserved", "dhcp-reserved"] = "static",
        configuration_id: int | None = None,
    ):
        match address_type:
            case "static":
                action = IPAssignmentActionValues.MAKE_STATIC
            case "reserved":
                action = IPAssignmentActionValues.MAKE_RESERVED
            case "dhcp-reserved":
                action = IPAssignmentActionValues.MAKE_DHCP_RESERVED
            case _:
                raise ValueError(f"Invalid action {address_type}")

        if not configuration_id:
            configuration_id = self.get_configuration()["id"]
        assert configuration_id is not None

        properties = {}

        if hostname:
            properties["name"] = hostname

        return self.client.assign_ip4_address(
            configuration_id=configuration_id,
            action=action,
            ip4_address=address,
            mac_address=mac_address,
            properties=properties,
        )


class Settings(BaseSettings):
    """Settings for the bluecat application."""

    url: str = Field("https://localhost")
    username: str = "admin"
    password: SecretStr = SecretStr("")

    class Config(BaseSettings.Config):
        app_name = "bluecat"

    def get_api_connection(self):
        return API(self.url, self.username, self.password.get_secret_value())
