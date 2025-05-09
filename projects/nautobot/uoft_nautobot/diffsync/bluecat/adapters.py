import typing as t

from nautobot_ssot.jobs import DataSource
from diffsync import DiffSync
from netaddr import IPRange
from nautobot.ipam.models import Prefix, IPAddress
from uoft_bluecat import Settings as BluecatSettings

from .models import BluecatNetwork, NautobotNetwork, BluecatAddress, NautobotAddress


class Bluecat(DiffSync):  # pylint: disable=missing-class-docstring
    network = BluecatNetwork
    address = BluecatAddress

    top_level: t.ClassVar = ["network", "address"]

    def __init__(self, job: DataSource | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        self.client = BluecatSettings.from_cache().get_api_connection()

        self.load()

    def load(self):
        """Load data from Bluecat API"""
        # for network in data:
        for network in self.client.yield_ip_object_list():
            if network["name"] is None:
                network["name"] = "UNNAMED"
            match network:
                case {"type": "IP4Block" | "IP6Block", **kwargs}:
                    status = "Container"
                case {"name": name, **kwargs} if "reserved" in name.lower():  # pyright: ignore[reportOptionalMemberAccess]
                    status = "Reserved"
                case _:
                    status = "Active"
            match network["properties"]:
                case {"CIDR": cidr, **kwargs}:
                    # IPv4 standard
                    prefix = cidr
                case {"prefix": cidr, **kwargs}:
                    # IPv6 standard
                    prefix = cidr
                case {"start": start, "end": end, **kwargs}:  # noqa: F841
                    # this IPBlock is a range, with a start and end address.
                    # May represent one or more CIDR prefixes.
                    prefixes = IPRange(start, end).cidrs()
                    raise Exception(
                        f"{network['name']}(Object ID {network['id']}) error: \
                        {network['type']}s of type 'range' are not supported.\
                        Recommend you split this into multiple objects: {prefixes}"
                    )
                case _:
                    raise Exception(
                        f"{network['name']}(Object ID {network['id']}) error: \
                        network properties object shape not recognized"
                    )
            self.add(
                self.network(
                    prefix=str(prefix).lower(),
                    name=network["name"],
                    status=status,
                )
            )
            self.load_addresses_for(network)

    def load_addresses_for(self, network):
        for address in self.client.yield_ip_address_list(network):
            if address is None:
                continue
            match address["properties"]["state"]:
                case "DHCP_RESERVED":
                    status = "DHCP"
                case "RESERVED":
                    status = "Reserved"
                case "GATEWAY":
                    status = "Active"
                case "STATIC":
                    status = "Active"
                case _:
                    raise Exception(
                        f"{address['name']}(Object ID {address['id']}) error: \
                            address properties state not recognized: {address['properties']['state']}"
                    )
            if address["name"] is None:
                address["name"] = ""
            self.add(
                self.address(
                    address=address["address"],
                    name=address["name"],
                    status=status,
                    bluecat_id=address["id"],
                )
            )


class Nautobot(DiffSync):  # pylint: disable=missing-class-docstring
    network = NautobotNetwork
    address = NautobotAddress

    top_level: t.ClassVar = ["network", "address"]

    def __init__(self, job: DataSource | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        self.load()

    def load(self):
        """Load data from nautobot's DB"""
        for pf in Prefix.objects.all():
            assert pf.cidr_str is not None
            self.add(
                self.network(
                    prefix=pf.cidr_str.lower(),
                    name=pf.description,
                    status=pf.status.name,
                    pk=pf.pk,
                )
            )
        for ip in IPAddress.objects.all():
            # assert address.address is not None
            self.add(
                self.address(
                    address=str(ip.address),
                    name=ip.description,
                    status=ip.status.name,
                    pk=ip.pk,
                )
            )
