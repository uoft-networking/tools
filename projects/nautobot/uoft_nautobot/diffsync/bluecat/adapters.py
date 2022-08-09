from django.conf import settings
from nautobot_ssot.jobs import DataSource
from diffsync import DiffSync
from netaddr import IPRange
from nautobot.ipam.models import Prefix
from uoft_core import shell
from uoft_core._vendor.bluecat_libraries.address_manager.api import Client
from uoft_core._vendor.bluecat_libraries.address_manager.constants import ObjectType

from .models import BluecatNetwork, NautobotNetwork


class Bluecat(DiffSync):  # pylint: disable=missing-class-docstring

    network = BluecatNetwork

    top_level = ["network"]

    def __init__(self, job: DataSource | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        conf = settings.PLUGINS_CONFIG["uoft_nautobot"]["bluecat"]
        client = Client(url=conf["url"])
        client.login(
            username=conf["username"],
            password=conf["password"],
        )
        self.client = client

        self.container_types = [
            ObjectType.IP4_BLOCK,
            ObjectType.IP6_BLOCK,
        ]
        self.all_types = [
            ObjectType.IP4_NETWORK,
            ObjectType.IP6_NETWORK,
            ObjectType.IP4_IP_GROUP,
        ] + self.container_types

        self.load()

        # if include_addresses:
        #     container_types = [
        #         ObjectType.IP4_BLOCK,
        #         ObjectType.IP6_BLOCK,
        #         ObjectType.IP4_NETWORK,
        #         ObjectType.IP6_NETWORK,
        #         ObjectType.IP4_IP_GROUP,
        #     ]
        #     all_types = [
        #         ObjectType.IP4_ADDRESS,
        #         ObjectType.IP6_ADDRESS,
        #     ] + container_types
        # else:
        #     container_types = [
        #         ObjectType.IP4_BLOCK,
        #         ObjectType.IP6_BLOCK,
        #     ]
        #     all_types = [
        #         ObjectType.IP4_NETWORK,
        #         ObjectType.IP6_NETWORK,
        #         ObjectType.IP4_IP_GROUP,
        #     ] + container_types

    def get_all_entities(self, parent_id, typ, start=0):
        page_size = 100
        entities = self.client.get_entities(
            parent_id, typ, start=start, count=page_size
        )
        yield from entities
        if len(entities) == page_size:
            if self.job:
                self.job.log("paging...")
            yield from self.get_all_entities(parent_id, typ, start=start + page_size)

    def yield_ip_object_tree(self, parent_id):
        for typ in self.all_types:
            for entity in self.get_all_entities(parent_id, typ):
                if typ in self.container_types:
                    if self.job:
                        self.job.log(f"Loading entries from {typ} {entity['name']}")
                    yield dict(
                        entity, children=list(self.yield_ip_object_tree(entity["id"]))
                    )
                else:
                    yield entity

    def yield_ip_object_list(self, parent_id=None):
        if parent_id is None:
            parent_id = self.client.get_entities(0, ObjectType.CONFIGURATION)[0]["id"]
        for typ in self.all_types:
            for entity in self.get_all_entities(parent_id, typ):
                yield entity
                if typ in self.container_types:
                    if self.job:
                        self.job.log(f"Loading entries from {typ} {entity['name']}")
                    yield from self.yield_ip_object_list(entity["id"])

    def load(self):
        """Load data from Bluecat API"""
        # temp until i get the sync job working, then I'll implement the bluecat api
        from pickle import loads  # noqa
        from pathlib import Path  # noqa

        # file = Path(__file__).parent.joinpath('bluecat-no-addresses.pkl')
        # data = loads(file.read_bytes())
        # for network in data:
        for network in self.yield_ip_object_list():
            if network["name"] is None:
                network["name"] = "UNNAMED"
            match network:
                case {"type": "IP4Block" | "IP6Block", **kwargs}:
                    status = "container"
                case {"name": name, **kwargs} if "reserved" in name.lower():
                    status = "reserved"
                case _:
                    status = "active"
            match network["properties"]:
                case {"CIDR": cidr, **kwargs}:
                    # IPv4 standard
                    prefix = cidr
                case {"prefix": cidr, **kwargs}:
                    # IPv6 standard
                    prefix = cidr
                case {"start": start, "end": end, **kwargs}:
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
            try:
                self.add(
                    self.network(
                        id=network["id"],
                        prefix=str(prefix).lower(),
                        name=network["name"],
                        status=status,
                    )
                )
            except Exception as e:
                raise e  # add noop handler for breakpoint


class Nautobot(DiffSync):  # pylint: disable=missing-class-docstring

    network = NautobotNetwork

    top_level = ["network"]

    def __init__(self, job: DataSource | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job = job
        self.qs = Prefix.objects.all()
        self.load()

    def load(self):
        """Load data from nautobot's DB"""
        for pf in self.qs:
            if not pf.cf.get("bluecat_id"):
                if self.job:
                    self.job.log_warning(f"{pf.prefix} has no bluecat_id")
                continue
            try:
                self.add(
                    self.network(
                        id=pf.cf["bluecat_id"],
                        prefix=pf.cidr_str.lower(),
                        name=pf.description,
                        status=pf.status.slug,
                        pk=pf.pk,
                    )
                )
            except Exception as e:
                raise e
