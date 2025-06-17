from typing import Optional, Literal, Any
from logging import getLogger

from uoft_nautobot import Settings

from diffsync import DiffSync
from netaddr import IPNetwork
from nautobot.ipam.models import Prefix, IPAddress
from nautobot.extras.models import Status, Tag, Note
from nautobot.core.choices import ColorChoices
from nautobot_ssot.contrib import NautobotModel as NautobotModelBase, NautobotAdapter
from nautobot_ssot.jobs import DataSource

logger = getLogger(__name__)


class NautobotModel(NautobotModelBase):

    def delete(self, nautobot_object: Any): # pyright: ignore[reportIncompatibleMethodOverride]
        """Safe delete an object, by adding tags or changing it's default status.

        Args:
            nautobot_object (Any): Any type of Nautobot object
        """
        safe_delete_status = Status.objects.get(name="Deprecated")
        if hasattr(nautobot_object, "status"):
            if not nautobot_object.status == safe_delete_status:
                nautobot_object.status = safe_delete_status
                logger.warning(
                    f"{nautobot_object} has changed status to {safe_delete_status}."
                )
        else:
            # Not everything has a status. This may come in handy once more models are synced.
            logger.warning(f"{nautobot_object} has no Status attribute.")

        if hasattr(nautobot_object, "tags"):
            ssot_safe_tag, _ = Tag.objects.get_or_create(
                name="SSoT Safe Delete",
                defaults={
                    "description": "Safe Delete Mode tag to flag an object, but not delete from Nautobot.",
                    "color": ColorChoices.COLOR_RED,
                },
            )
            object_tags = nautobot_object.tags.all()
            # No exception raised for empty iterator, safe to do this any
            if not any(
                obj_tag for obj_tag in object_tags if obj_tag.name == ssot_safe_tag.name
            ):
                nautobot_object.tags.add(ssot_safe_tag)
                logger.warning(f"Tagging {nautobot_object} with `SSoT Safe Delete`.")

        if hasattr(nautobot_object, "notes"):
            Note.objects.create(
                assigned_object=nautobot_object,
                note=f"SSoT Safe Delete: {nautobot_object} has been flagged for deletion by the Bluecat SSoT job.",
            )

        nautobot_object.save()
        return self


class RemoteAdapter(DiffSync):
    def __init__(self, *args, job, sync=None, **kwargs):
        """Instantiate this class, but do not load data immediately from the system."""
        super().__init__(*args, **kwargs)
        self.job = job
        self.sync = sync
        self.client = Settings().from_cache().bluecat.get_api_connection()


class PrefixModel(NautobotModel):
    """
    Shared data model representing
    what Bluecat calls an IP Block or IP Network,
    and nautobot calls a Prefix.
    """

    # Metadata about this model
    _model = Prefix  # pyright: ignore[reportAssignmentType]
    _modelname = "prefix"
    _identifiers = ("prefix",)
    _attributes = (
        "description",
        "type",
        "status__name",
    )
    _synthetic_parameters = ("prefix",)

    # Data type declarations for all identifiers and attributes

    prefix: IPNetwork  # ip address, in cidr notation
    # network: str  # ip address, in cidr notation
    # broadcast: str  # ip address, in cidr notation, always the last ip in the network, even in /31 and /32 "networks"
    # prefix_length: int
    # ip_version: Literal[4, 6]
    description: Optional[str]
    type: Literal["container", "network", "pool"]
    status__name: Literal["Active", "Reserved", "Deprecated", "Container"]
    # location__name: Optional[str]
    # vlan__name: Optional[str]


class IPAddressModel(NautobotModel):
    """
    Shared data model representing IP Address objects in Nautobot and Bluecat.
    """

    # Metadata about this model
    _model = IPAddress  # pyright: ignore[reportAssignmentType]
    _modelname = "address"
    _identifiers = ("address",)
    _attributes = ("status__name", "type", "dns_name")
    _synthetic_parameters = ("address",)

    # Data type declarations for all identifiers and attributes

    address: IPNetwork  # ip address, in cidr notation
    status__name: Literal["Active", "Reserved", "Deprecated"]
    type: Literal["host", "dhcp", "slaac"]
    dns_name: Optional[str]
    # assigned_object__name: Optional[str]


class Nautobot(NautobotAdapter):
    top_level = ("prefix", "address")  # pyright: ignore[reportAssignmentType]

    prefix = PrefixModel
    address = IPAddressModel

    def _load_single_object(self, database_object, diffsync_model, parameter_names):
        from pydantic.v1 import ValidationError

        """Load a single diffsync object from a single database object."""
        parameters = {}
        for parameter_name in parameter_names:
            if (
                hasattr(diffsync_model, "_synthetic_parameters")
                and parameter_name in diffsync_model._synthetic_parameters
            ):
                parameters[parameter_name] = getattr(database_object, parameter_name)
            else:
                self._handle_single_parameter(
                    parameters, parameter_name, database_object, diffsync_model
                )
        try:
            diffsync_model = diffsync_model(**parameters)
        except ValidationError as error:
            raise ValueError(f"Parameters: {parameters}") from error
        self.add(diffsync_model)

        self._handle_children(database_object, diffsync_model)
        return diffsync_model


class Bluecat(RemoteAdapter):
    top_level = ("prefix", "address")  # pyright: ignore[reportAssignmentType]

    prefix = PrefixModel
    address = IPAddressModel

    def load(self):
        self._load_networks_from_bluecat()

    def _load_networks_from_bluecat(self):
        for bluecat_net_info in self.client.yield_ip_object_list():
            if bluecat_net_info["name"] is None:
                bluecat_net_info["name"] = "UNNAMED"
            status = "Active"
            type = "network"
            if bluecat_net_info["type"] in ["IP4Block", "IP6Block"]:
                type = "container"
            if "reserved" in bluecat_net_info["name"].lower():
                status = "Reserved"
            if "CIDR" in bluecat_net_info["properties"]:
                cidr = bluecat_net_info["properties"]["CIDR"]
            elif "prefix" in bluecat_net_info["properties"]:
                cidr = bluecat_net_info["properties"]["prefix"]
            else:
                raise Exception(
                    f"{bluecat_net_info['name']}(Object ID {bluecat_net_info['id']}) error: \
                    Network type not supported. Only IP4Block and IP6Block are supported."
                )
            self.add(
                self.prefix(
                    prefix=IPNetwork(cidr),
                    description=bluecat_net_info["name"],
                    type=type,
                    status__name=status,
                ) # pyright: ignore[reportCallIssue]
            )
            self._load_addresses_for_network(bluecat_net_info)

    def _load_addresses_for_network(self, network):
        for bluecat_ip_info in self.client.yield_ip_address_list(network):
            if bluecat_ip_info is None:
                continue
            status = "Active"
            type = "host"
            match bluecat_ip_info["properties"]["state"]:
                case "DHCP_RESERVED":
                    type = "dhcp"
                case "RESERVED":
                    status = "Reserved"
            if bluecat_ip_info["name"] is None:
                bluecat_ip_info["name"] = ""
            self.add(
                self.address(
                    address=IPNetwork(bluecat_ip_info["address"]),
                    dns_name=bluecat_ip_info["name"],
                    status__name=status,
                    type=type,
                )  # pyright: ignore[reportCallIssue]
            )


class BluecatToNautobot(DataSource):

    def load_source_adapter(self):
        self.source_adapter = Bluecat(job=self)
        self.source_adapter.load()

    def load_target_adapter(self):
        self.target_adapter = Nautobot(job=self)
        self.target_adapter.load()
