from typing import Literal, TypedDict, Iterator
from logging import getLogger

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr
from uoft_core._vendor.bluecat_libraries.address_manager.api import Client
from uoft_core._vendor.bluecat_libraries.address_manager.constants import (
    IPAssignmentActionValues,
    ObjectType,
    OptionType,
)

logger = getLogger(__name__)

CONTAINER_TYPES = [
    ObjectType.IP4_BLOCK,
    ObjectType.IP6_BLOCK,
]
ALL_NETWORK_TYPES = [
    ObjectType.IP4_NETWORK,
    ObjectType.IP6_NETWORK,
    ObjectType.IP4_IP_GROUP,
    *CONTAINER_TYPES,
]

ADDRESS_TYPES = [
    ObjectType.IP4_ADDRESS,
    ObjectType.IP6_ADDRESS,
]


class APIEntity(TypedDict):
    id: int
    name: str | None
    type: ObjectType
    properties: dict[str, str]


class Network(APIEntity, total=False):
    children: list["Network"]


class Address(APIEntity):
    address: str


class API:
    """This class is a wrapper around the bluecat_libraries.address_manager.api.Client class"""

    def __init__(self, url, username, password) -> None:
        self.client = Client(url)
        self.client.login(username, password)

    def get_configuration(self, name: str | None = None):
        """Get a configuration by name, or the first available configuration if no name is provided"""
        if name:
            return self.client.get_entity_by_name(0, name, ObjectType.CONFIGURATION)
        return next(self.get_entities(0, ObjectType.CONFIGURATION))

    def get_entities(self, parent_id, typ, start=0):
        page_size = 100
        entities = self.client.get_entities(
            parent_id, typ, start=start, count=page_size
        )
        yield from entities
        if len(entities) == page_size:
            logger.info(f"Getting more {typ} entries from {start + page_size}")
            yield from self.get_entities(parent_id, typ, start=start + page_size)

    def yield_ip_object_tree(self, parent_id) -> Iterator[Network]:
        for typ in ALL_NETWORK_TYPES:
            for entity in self.get_entities(parent_id, typ):  # type: ignore
                if typ in CONTAINER_TYPES:
                    yield dict(
                        entity, children=list(self.yield_ip_object_tree(entity["id"]))
                    )  # type: ignore
                yield entity  # type: ignore

    def yield_ip_object_list(self, parent_id=None) -> Iterator[APIEntity]:
        if parent_id is None:
            parent_id = self.get_configuration()["id"]
        for typ in ALL_NETWORK_TYPES:
            for entity in self.get_entities(parent_id, typ):
                yield entity  # type: ignore
                if typ in CONTAINER_TYPES:
                    yield from self.yield_ip_object_list(entity["id"])

    def yield_ip_address_list(self, parent) -> Iterator[Address]:
        parent_id = parent["id"]
        if list(self.client.get_entities(parent_id, ObjectType.DHCP4_RANGE)):
            # we don't want to sync DHCP-assigned addresses
            return

        if list(self.client.get_entities(parent_id, ObjectType.DHCP6_RANGE)):
            # we don't want to sync DHCP-assigned addresses
            return

        for typ in ADDRESS_TYPES:
            for entity in self.get_entities(parent_id, typ):
                _props = parent["properties"]
                try:
                    _cidr = _props["CIDR"]
                except KeyError:
                    _cidr = _props["prefix"]
                prefix_len = _cidr.split("/")[1]
                address = entity["properties"]["address"]
                cidr = f"{address}/{prefix_len}"
                yield dict(entity, address=cidr)  # type: ignore

    def yield_all_ip_addresses(self):
        for network in self.yield_ip_object_list():
            for address in self.yield_ip_address_list(network):
                yield address

    def get_ipv4_address(
        self,
        address: str,
        configuration_id: int | None = None,
    ):
        if not configuration_id:
            configuration_id = self.get_configuration()["id"]
        assert configuration_id is not None

        return self.client.get_entity_by_cidr(
            cidr=f"{address}/32",
            type=ObjectType.IP4_ADDRESS,
            parent_id=configuration_id,
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
