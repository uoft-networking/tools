from typing import Literal, TypedDict, Iterator, Callable, overload
from logging import getLogger
import concurrent.futures
import threading
from functools import cached_property
import asyncio
from importlib.metadata import version

from uoft_core import BaseSettings, Field
from uoft_core.types import SecretStr, IPNetwork, IPAddress
from uoft_core._vendor.bluecat_libraries.address_manager.api import Client
from uoft_core._vendor.bluecat_libraries.address_manager import constants
from uoft_core._vendor.bluecat_libraries.http_client.exceptions import ErrorResponse

logger = getLogger(__name__)

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
__version__ = version(__package__) # type: ignore

CONTAINER_TYPES = [
    constants.ObjectType.IP4_BLOCK,
    constants.ObjectType.IP6_BLOCK,
]
ALL_NETWORK_TYPES = [
    constants.ObjectType.IP4_NETWORK,
    constants.ObjectType.IP6_NETWORK,
    constants.ObjectType.IP4_IP_GROUP,
    *CONTAINER_TYPES,
]

ADDRESS_TYPES = [
    constants.ObjectType.IP4_ADDRESS,
    constants.ObjectType.IP6_ADDRESS,
]

ALL_IP_OBJECTS = ALL_NETWORK_TYPES + ADDRESS_TYPES


class APIEntity(TypedDict):
    id: int
    name: str | None
    type: constants.ObjectType
    properties: dict[str, str]


class Network(APIEntity, total=False):
    children: list["Network"]


class Address(APIEntity):
    address: str


#TODO: replace all this garbage with a mult-threaded API wrapper on the V2 rest api, 
# delete vendored bluecat libraries from uoft_core

class API:
    """This class is a wrapper around the bluecat_libraries.address_manager.api.Client class"""

    constants = constants  # attach the constants to the class for easy access

    def __init__(self, url, username, password, dhcp_only_network_ids) -> None:
        self.url = url
        self.dhcp_only_network_ids = dhcp_only_network_ids
        self.client = Client(url)
        self.login(username, password)

    def login(self, username, password):
        # this method is here to allow the multi-threaded API to override it
        self.client.login(username, password)

    def get_configuration(self, name: str | None = None):
        """Get a configuration by name, or the first available configuration if no name is provided"""
        if name:
            logger.info(f"Bluecat: getting configuration by name: {name}")
            return self.client.get_entity_by_name(
                0, name, constants.ObjectType.CONFIGURATION
            )
        logger.info("Bluecat: getting first available configuration")
        return next(self.get_entities(0, constants.ObjectType.CONFIGURATION))

    @cached_property
    def configuration_id(self):
        id_ = self.get_configuration()["id"]
        assert isinstance(id_, int)
        return id_

    def get_view(self, name: str | None = None, parent_id: int | None = None):
        """Get a view by name, or the first available view if no name is provided"""
        if parent_id is None:
            parent_id = self.configuration_id
        assert parent_id is not None
        if name:
            logger.info(f"Bluecat: getting view by name: {name}")
            return self.client.get_entity_by_name(
                parent_id, name, constants.ObjectType.VIEW
            )
        logger.info("Bluecat: getting first available view")
        return next(self.get_entities(parent_id, constants.ObjectType.VIEW))

    @cached_property
    def default_view_id(self):
        return self.get_view()["id"]

    def get_entities(self, parent_id, typ, start=0):
        page_size = 1000
        if parent_id in self.dhcp_only_network_ids:
            logger.info(f"Bluecat: skipping entities in DHCP-only network {parent_id}")
            return
        if not start:
            logger.debug(f"Bluecat: getting {typ} entries from parent {parent_id}")
        entities = self.client.get_entities(
            parent_id, typ, start=start, count=page_size
        )
        for entity in entities:
            entity["parent_id"] = parent_id
            yield entity
        if len(entities) == page_size:
            if all(["DHCP" in e["properties"].get("state", "") for e in entities[1:]]):
                logger.warning(
                    f"network container {parent_id} contains only DHCP-assigned addresses... "
                    "you may want to add it to dhcp_only_network_ids set"
                )
            logger.info(f"Bluecat: getting more {typ} entries from {start + page_size}")
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
            parent_id = self.configuration_id
        for typ in ALL_IP_OBJECTS:
            for entity in self.get_entities(parent_id, typ):
                entity["parent_id"] = parent_id
                yield entity  # type: ignore
                if typ in ALL_NETWORK_TYPES:
                    yield from self.yield_ip_object_list(entity["id"])

    def yield_dns_object_tree(self, parent_id=None) -> Iterator[Network]:
        if parent_id is None:
            parent_id = self.get_view()["id"]
        for typ in [constants.ObjectType.ZONE, constants.ObjectType.HOST_RECORD]:
            for entity in self.get_entities(parent_id, typ):  # type: ignore
                if typ is constants.ObjectType.ZONE:
                    yield dict(
                        entity, children=list(self.yield_dns_object_tree(entity["id"]))
                    )  # type: ignore
                yield entity  # type: ignore

    def yield_dns_object_list(self, parent_id=None) -> Iterator[APIEntity]:
        if parent_id is None:
            parent_id = self.get_view()["id"]
        for typ in [constants.ObjectType.ZONE, constants.ObjectType.HOST_RECORD]:
            for entity in self.get_entities(parent_id, typ):
                yield entity  # type: ignore
                if typ in constants.ObjectType.ZONE:
                    yield from self.yield_dns_object_list(entity["id"])

    def yield_ip_address_list(self, parent) -> Iterator[Address]:
        parent_id = parent["id"]
        # if list(self.client.get_entities(parent_id, ObjectType.DHCP4_RANGE)):
        #     # we don't want to sync DHCP-assigned addresses
        #     return

        # if list(self.client.get_entities(parent_id, ObjectType.DHCP6_RANGE)):
        #     # we don't want to sync DHCP-assigned addresses
        #     return

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
            configuration_id = self.configuration_id
        assert configuration_id is not None

        return self.client.get_entity_by_cidr(
            cidr=f"{address}/32",
            type=constants.ObjectType.IP4_ADDRESS,
            parent_id=configuration_id,
        )

    def create_prefix(
        self,
        net: IPNetwork,
        name: str,
        type: Literal["container", "network", "pool"],
        parent_id: int,
        configuration_id: int | None = None,
    ):
        if not configuration_id:
            configuration_id = self.configuration_id
        assert configuration_id is not None

        prefix = str(net)
        if net.version == 4:
            if type == "container":
                new_id = self.client.add_ip4_block_by_cidr(
                    entity_id=parent_id,
                    cidr=prefix,
                    properties=dict(name=name),
                )
            elif type == "network":
                new_id = self.client.add_ip4_network(
                    ip4_block_id=parent_id,
                    cidr=prefix,
                    properties=dict(name=name),
                )
            else:
                # pool
                raise NotImplementedError
                new_id = self.client.add_ip4_ip_group_by_range()
        else:
            if type == "container":
                new_id = self.client.add_ip6_block_by_prefix(
                    parent_ip6_block_id=parent_id,
                    prefix=prefix,
                    name=name,
                )
            elif type == "network":
                new_id = self.client.add_ip6_network_by_prefix(
                    ip6_block_id=parent_id,
                    prefix=prefix,
                    name=name,
                )
        return new_id

    def assign_ipv4_address(
        self,
        address: str,
        mac_address: str | None = None,
        hostname: str | None = None,
        address_type: Literal["static", "reserved", "dhcp-reserved"] = "static",
        domain: str = "netmgmt.utsc.utoronto.ca",
        configuration_id: int | None = None,
    ):

        if not configuration_id:
            configuration_id = self.configuration_id

        match address_type:
            case "static":
                action = constants.IPAssignmentActionValues.MAKE_STATIC
            case "reserved":
                action = constants.IPAssignmentActionValues.MAKE_RESERVED
            case "dhcp-reserved":
                action = constants.IPAssignmentActionValues.MAKE_DHCP_RESERVED
            case _:
                raise ValueError(f"Invalid action {address_type}")

        properties = {}

        if hostname:
            properties["name"] = hostname

        return self.client.assign_ip4_address(
            configuration_id=configuration_id,
            action=action,
            ip4_address=address,
            mac_address=mac_address,
            host_info=[
                f"{hostname}.{domain}",  # FQDN
                self.default_view_id,  # view_id
                True,  # reverse PTR record flag
                False,  # "sameAsZoneFlag"
            ],
            properties=properties,
        )

    def assign_ipv6_address(
        self,
        address: str,
        mac_address: str | None = None,
        hostname: str | None = None,
        address_type: Literal["static", "reserved", "dhcp-reserved"] = "static",
        domain: str = "netmgmt.utsc.utoronto.ca",
        configuration_id: int | None = None,
    ):

        if not configuration_id:
            configuration_id = self.configuration_id

        match address_type:
            case "static":
                action = constants.IPAssignmentActionValues.MAKE_STATIC
            case "reserved":
                action = constants.IPAssignmentActionValues.MAKE_RESERVED
            case "dhcp-reserved":
                action = constants.IPAssignmentActionValues.MAKE_DHCP_RESERVED
            case _:
                raise ValueError(f"Invalid action {address_type}")

        properties = {}
        host_info = None

        if hostname:
            properties["name"] = hostname
            host_info = [
                self.get_view()["id"],  # view_id
                f"{hostname}.{domain}",  # FQDN
                False,  # "sameAsZoneFlag"
                True,  # reverse PTR record flag
            ]

        return self.client.assign_ip6_address(
            entity_id=configuration_id,
            address=str(address),
            action=action,
            host_info=host_info,
            properties=dict(name=hostname),
        )

    def assign_address(
        self,
        address: IPAddress | str,
        hostname: str,
        mac_address: str | None = None,
        configuration_id: int | None = None,
        domain: str = "netmgmt.utsc.utoronto.ca",
    ):
        if isinstance(address, str):
            address = IPAddress(address)

        if not configuration_id:
            configuration_id = self.configuration_id

        params = dict(
            address=str(address),
            mac_address=mac_address,
            hostname=hostname,
            configuration_id=configuration_id,
            domain=domain,
        )

        try:
            if address.version == 4:
                return self.assign_ipv4_address(**params) # type: ignore
            else:
                return self.assign_ipv6_address(**params) # type: ignore
        except ErrorResponse as e:
            if 'Duplicate of another item' in e.message:
                # TODO: reassign address
                raise e
            else:
                raise e


class MultiThreadedAPI(API):
    """API wrapper that runs all methods in a ThreadPoolExecutor."""

    ns = threading.local()
    loop: asyncio.AbstractEventLoop
    main_thread: threading.Thread

    def __init__(self, *args, **kwargs):
        self.main_thread = threading.current_thread()
        super().__init__(*args, **kwargs)
        self.pool = concurrent.futures.ThreadPoolExecutor(
            # Based on preliminary testing, 6 threads seems to be the sweet spot for performance
            # single-threaded (no DHCP): 78.6s
            # multi-threaded (4 threads): 46.1s (bluecat CPU peak: 70-80%)
            # multi-threaded (6 threads): 37.4s (bluecat CPU peak: 87%)
            # multi-threaded (8 threads): 35.6s (bluecat CPU peak: 101%)
            # multi-threaded (12 threads): 33.2s (bluecat CPU peak: 104%)
            max_workers=6,
            thread_name_prefix="bluecat_api",
        )

    @property
    def client(self) -> Client:
        if not hasattr(self.ns, "client"):
            self.ns.client = Client(self.url)
            self.ns.client._raw_api.session.headers.update(
                self._client._raw_api.session.headers
            )
        if threading.current_thread() == self.main_thread:
            return self._client
        return self.ns.client

    @client.setter
    def client(self, value):
        self._client = value

    def get_entities_list(self, parent_id, typ, start=0):
        # this method exists to ensure that the self.get_entities generator is consumed within the threadpool
        # instead of being returned to the main thread
        return list(self.get_entities(parent_id, typ, start))

    def fetch_all_child_objects(
        self,
        futures: list,
        parent_id: int,
        object_types_to_fetch: list[constants.ObjectType],
        object_types_to_recurse_into,
    ):

        for typ in object_types_to_fetch:
            fut = self.pool.submit(self.get_entities_list, parent_id, typ)

            def callback(fut):
                # for every fetched entity which is a network type, add a job to the work queue
                # to fetch its children (subnetworks and ip addresses)
                res = fut.result()
                for entity in res:
                    if entity["type"] in object_types_to_recurse_into:
                        self.fetch_all_child_objects(
                            futures,
                            entity["id"],
                            object_types_to_fetch,
                            object_types_to_recurse_into,
                        )

            fut.add_done_callback(callback)
            futures.append(fut)

    def queue_ip_objects(self, futures, parent_id):
        self.fetch_all_child_objects(
            futures, parent_id, ALL_IP_OBJECTS, ALL_NETWORK_TYPES
        )

    def get_ip_objects(self):
        """Get all IP objects in the default configuration"""
        configuration_id = self.configuration_id
        futures = []
        results = []
        self.queue_ip_objects(futures, configuration_id)
        while futures:
            for future in concurrent.futures.as_completed(futures):
                futures.remove(future)
                entities = future.result()
                for entity in entities:
                    results.append(dict(entity))
        return results

    def queue_dns_objects(self, futures, parent_id):
        self.fetch_all_child_objects(
            futures,
            parent_id,
            [constants.ObjectType.ZONE, constants.ObjectType.HOST_RECORD],
            [constants.ObjectType.ZONE],
        )

    def get_dns_objects(self):
        """Get all IP objects in the default configuration"""
        view_id = self.get_view()["id"]
        futures = []
        results = []
        self.queue_dns_objects(futures, view_id)
        while futures:
            for future in concurrent.futures.as_completed(futures):
                futures.remove(future)
                entities = future.result()
                for entity in entities:
                    results.append(dict(entity))
        return results

    def multithread_jobs(self, *jobs: Callable):
        from uoft_core import Timeit

        t = Timeit()
        with self.pool:
            self.main_thread = threading.current_thread()
            futures = [self.pool.submit(job) for job in jobs]
            results = [fut.result() for fut in futures]
        multithread_runtime = t.interval().str
        logger.info(
            f"Bluecat jobs {[j.__name__ for j in jobs]} complete. runtime: {multithread_runtime}"
        )
        return results


class Settings(BaseSettings):
    """Settings for the bluecat application."""

    url: str = Field("https://localhost")
    username: str = "admin"
    password: SecretStr = SecretStr("")
    dhcp_only_network_ids: list[int] = Field(
        default_factory=set,
        description="Network IDs that contain only DHCP-assigned addresses",
    )

    class Config(BaseSettings.Config):
        app_name = "bluecat"

    @overload
    def get_api_connection(self, multi_threaded: Literal[False]) -> API: ...

    @overload
    def get_api_connection(self, multi_threaded: Literal[True]) -> MultiThreadedAPI: ...

    @overload
    def get_api_connection(self) -> API: ...

    def get_api_connection(self, multi_threaded=False):
        args = (
            self.url,
            self.username,
            self.password.get_secret_value(),
            self.dhcp_only_network_ids,
        )
        if multi_threaded:
            return MultiThreadedAPI(*args)
        return API(*args)


class STGSettings(Settings):

    class Config(BaseSettings.Config):
        app_name = "bluecat-stg"
