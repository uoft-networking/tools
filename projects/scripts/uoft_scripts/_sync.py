"""
so it goes like this:

this module has three main classes: 

the base SyncManager class contains the main synchronization logic, 
and contains a source and destination instance of Target subclasses.

each subclass is responsible for loading data from the respective systems, 
and for creating, updating, and deleting objects in the respective systems.

the core approach to synchronization is to initialize one instance of each subclass, 
and then call the synchronize method on the sync manager instance.

Full two-way synchronization is done by loading data from both systems,
calling the synchronize method on the destination manager instance,
and then calling the synchronize method on the source manager instance.
"""

import logging
import typing
import threading
import re
import concurrent.futures as cf

from uoft_core.types import IPNetwork, IPAddress, BaseModel, SecretStr
from uoft_core import BaseSettings, Field, Prompt
from uoft_bluecat import Settings as BluecatSettings

import pynautobot
import pynautobot.core.endpoint
from pynautobot.core.response import Record
import requests
import deepdiff
import deepdiff.model
import typer


class NautobotCLISettings(BaseSettings):
    """Settings for the nautobot_cli application."""

    url: str = Field(..., title="Nautobot server URL")
    token: SecretStr = Field(..., title="Nautobot API Token")

    class Config(BaseSettings.Config):
        app_name = "nautobot-cli"


logger = logging.getLogger(__name__)

app = typer.Typer(name="nautobot")

ip_address_as_str: typing.TypeAlias = str
"ip address, e.g. '192.168.0.20'"
network_prefix_as_str: typing.TypeAlias = str
"network prefix in CIDR notation, e.g. '10.0.0.0/8'"
CommonID: typing.TypeAlias = ip_address_as_str | network_prefix_as_str
"common id used to identify objects in both systems"

Status: typing.TypeAlias = typing.Literal["Active", "Reserved", "Deprecated"]
PrefixType: typing.TypeAlias = typing.Literal["container", "network", "pool"]


OnOrphanAction: typing.TypeAlias = typing.Literal[
    "prompt", "delete", "backport", "skip"
]


class IPAddressModel(BaseModel):
    address: str  # CIDR notation
    prefixlen: int
    name: str
    status: Status
    dns_name: str


class PrefixModel(BaseModel):
    prefix: network_prefix_as_str
    description: str
    type: PrefixType
    status: Status


class DeviceModel(BaseModel):
    hostname: str
    ip_address: ip_address_as_str


Prefixes: typing.TypeAlias = dict[network_prefix_as_str, PrefixModel]
Addresses: typing.TypeAlias = dict[ip_address_as_str, IPAddressModel]
Devices: typing.TypeAlias = dict[str, DeviceModel]
DatasetName: typing.TypeAlias = typing.Literal["prefixes", "addresses", "devices"]


# models come from source and dest
class DatasetUpdate(typing.TypedDict):
    source: BaseModel
    dest: BaseModel


class Changes(BaseModel):
    # model comes from source
    create: dict[DatasetName, dict[CommonID, BaseModel]] = Field(default_factory=dict)

    update: dict[DatasetName, dict[CommonID, DatasetUpdate]] = Field(
        default_factory=dict
    )

    # model comes from dest
    delete: dict[DatasetName, dict[CommonID, BaseModel]] = Field(default_factory=dict)

    def is_empty(self):
        if self.create or self.update or self.delete:
            return False
        return True


class SyncData(BaseModel):
    prefixes: Prefixes | None
    addresses: Addresses | None
    devices: Devices | None

    # the keys will be ip addresses / network cidrs / dns names, and
    # the values will be bluecat object ids or nautobot uuids
    local_ids: dict[CommonID, int | str]


class Target:
    name: str
    syncdata: SyncData

    def __init_subclass__(cls) -> None:
        assert hasattr(cls, "name"), "Subclasses must define a name attribute"
        assert isinstance(cls.name, str), "name must be a string"

    def load_data(self, datasets: set[DatasetName]):
        raise NotImplementedError

    def create(self, records: dict[DatasetName, dict[CommonID, BaseModel]]):
        raise NotImplementedError

    def update(self, records: dict[DatasetName, dict[CommonID, DatasetUpdate]]):
        raise NotImplementedError

    def delete(self, records: dict[DatasetName, dict[CommonID, BaseModel]]):
        raise NotImplementedError


class SyncManager:
    syncdata: SyncData
    diff: deepdiff.DeepDiff
    source: Target
    dest: Target

    def __init__(
        self,
        source: Target,
        dest: Target,
        datasets: set[DatasetName],
        on_orphan: OnOrphanAction = "prompt",
    ) -> None:
        self.source = source
        self.dest = dest
        self.datasets = datasets
        self.diff = None  # type: ignore
        self.loaded = False
        self.on_orphan = on_orphan
        self.changes = Changes()

    def load(self):
        """Load data from both source and destination systems. This method should be called before synchronize."""
        with cf.ThreadPoolExecutor(thread_name_prefix="load_data") as executor:
            source_task = executor.submit(self.source.load_data, datasets=self.datasets)
            dest_task = executor.submit(self.dest.load_data, datasets=self.datasets)
            source_task.result()
            dest_task.result()
        self.loaded = True

    def synchronize(self):
        assert self.loaded, "Data must be loaded before synchronization can occur"

        logger.info("Comparing data between source and destination systems")
        for dataset in self.datasets:
            source_data = getattr(self.source.syncdata, dataset)
            dest_data = getattr(self.dest.syncdata, dataset)
            if source_data is None:
                continue
            if dest_data is None:
                dest_data = {}
            for common_id, source_record in source_data.items():
                dest_record = dest_data.get(common_id)
                if dest_record is None:
                    self.changes.create.setdefault(dataset, {})[
                        common_id
                    ] = source_record
                elif source_record != dest_record:
                    self.changes.update.setdefault(dataset, {})[common_id] = dict(  # type: ignore
                        source=source_record,
                        dest=dest_record,
                    )
            for common_id, dest_record in dest_data.items():
                if common_id not in source_data:
                    self.changes.delete.setdefault(dataset, {})[common_id] = dest_record
        logger.info("Data comparison complete")

        records_to_create = ", ".join(
            [
                f"{len(records)} {dataset}"
                for dataset, records in self.changes.create.items()
            ]
        )
        records_to_update = ", ".join(
            [
                f"{len(records)} {dataset}"
                for dataset, records in self.changes.update.items()
            ]
        )
        orphaned_records = ", ".join(
            [
                f"{len(records)} orphaned {dataset}"
                for dataset, records in self.changes.delete.items()
            ]
        )
        records_to_create = (
            f"{records_to_create} to create, " if records_to_create else ""
        )
        records_to_update = (
            f"{records_to_update} to update, " if records_to_update else ""
        )
        orphaned_records = (
            f"{orphaned_records} (records that exist in the destination system, but not in the source system)"
            if orphaned_records
            else ""
        )
        total_records = records_to_create + records_to_update + orphaned_records
        msg = (
            f"Found {total_records}"
            if total_records
            else "No records to synchronize, everything is in sync!"
        )
        logger.info(msg)

    def commit(self):
        assert self.changes is not None, "Synchronize must be called before commit"
        self.dest.create(self.changes.create)
        self.dest.update(self.changes.update)

        if self.changes.delete:
            self._handle_orphaned_records()

    def _handle_orphaned_records(self):
        orphaned_records = [
            f"{len(records)} {dataset}"
            for dataset, records in self.changes.delete.items()
            if records
        ]
        print(
            f"{', '.join(orphaned_records)} records were found in the destination system "
            f"({self.dest.name}), but not in the source system ({self.source.name})"
        )

        if self.on_orphan == "delete":
            logger.info("Deleting orphaned records from the destination system")
            self.dest.delete(self.changes.delete)
        elif self.on_orphan == "backport":
            logger.info("Backporting orphaned records to the source system")
            self.source.create(self.changes.delete)
        elif self.on_orphan == "skip":
            logger.info("Skipping orphaned records")
            pass
        elif self.on_orphan == "prompt":
            logger.warning(
                "Would you like to delete these records from the destination system, "
                "backport them to the source system, or skip them?"
            )
            choice = Prompt(history_cache=None).get_from_choices(
                "orphaned_record_action",
                ["delete", "backport", "skip"],
                description="What would you like to do?",
            )
            if choice == "delete":
                self.dest.delete(self.changes.delete)
            elif choice == "backport":
                self.source.create(self.changes.delete)
            elif choice == "skip":
                pass


class NautobotTarget(Target):
    name = "nautobot"

    def __init__(self, dev=False) -> None:
        if dev:
            NautobotCLISettings.Config.app_name = "nautobot-cli-dev"
        settings = NautobotCLISettings().from_cache()
        self.url = settings.url
        self.token = settings.token

        # used to store thread-local copies of the api object
        self._local_ns = threading.local()

        try:
            response = requests.get(self.url)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            print("need to run `./run nautobot. start` to start the nautobot server")
            exit(1)

    @property
    def api(self):
        # get a thread-local copy of the api object
        if not hasattr(self._local_ns, "api"):
            self._local_ns.api = pynautobot.api(
                self.url, token=self.token.get_secret_value()
            )
        return self._local_ns.api

    def load_data(self, datasets: set[DatasetName]):
        raw_data = self.load_data_raw(datasets)
        logger.info("Nautobot: Parsing and processing data")
        prefixes = {}
        addresses = {}
        devices = {}
        local_ids = {}
        local_ids["Global namespace"] = raw_data.global_namespace_id
        local_ids["Soft Delete tag"] = raw_data.soft_delete_tag_id
        for status_id, status in raw_data.statuses.items():
            local_ids[status] = status_id

        for nb_prefix in raw_data.prefixes:
            if nb_prefix["tags"] and raw_data.soft_delete_tag_id in [
                t["id"] for t in nb_prefix["tags"]
            ]:
                continue
            pfx = str(IPNetwork(nb_prefix["prefix"])).lower()
            status_id = nb_prefix["status"]["id"]
            local_ids[pfx] = nb_prefix["id"]
            prefixes[pfx] = PrefixModel(
                prefix=pfx,
                description=nb_prefix["description"],
                type=nb_prefix["type"]["value"],
                status=raw_data.statuses[status_id],
            )

        for nb_address in raw_data.addresses:
            if nb_address["tags"] and raw_data.soft_delete_tag_id in [
                t["id"] for t in nb_address["tags"]
            ]:
                continue
            obj = IPNetwork(nb_address["address"])
            addr = str(obj.ip).lower()
            status_id = nb_address["status"]["id"]
            local_ids[addr] = nb_address["id"]
            addresses[addr] = IPAddressModel(
                address=addr,
                prefixlen=obj.prefixlen,
                name=nb_address["description"],
                status=raw_data.statuses[status_id],
                dns_name=nb_address["dns_name"],
            )

        for nb_device in raw_data.devices:
            local_ids[nb_device["name"]] = nb_device["id"]
            if ip4 := nb_device.get("primary_ip4"):
                ip_addr_id = ip4["id"]
            elif ip6 := nb_device.get("primary_ip6"):
                ip_addr_id = ip6["id"]
            else:
                raise Exception(f"Device {nb_device['name']} has no primary IP address")
            ip_address = self.api.ipam.ip_addresses.get(ip_addr_id)["address"]  # type: ignore
            devices[nb_device["name"]] = dict(
                hostname=nb_device["name"], ip_address=ip_address
            )

        self.syncdata = SyncData(
            prefixes=prefixes or None,
            addresses=addresses or None,
            devices=devices or None,
            local_ids=local_ids,
        )

    def load_data_raw(self, datasets: set[DatasetName]):
        with cf.ThreadPoolExecutor(
            thread_name_prefix="nautobot_fetch_data"
        ) as executor:

            if "prefixes" in datasets:
                logger.info("Nautobot: Fetching all Prefixes")
                prefixes_task = executor.submit(lambda: self.api.ipam.prefixes.all())

            if "addresses" in datasets:
                logger.info("Nautobot: Fetching all IP Addresses")
                addresses_task = executor.submit(
                    lambda: self.api.ipam.ip_addresses.all()
                )

            if "devices" in datasets:
                logger.info("Nautobot: Fetching all Devices")
                devices_task = executor.submit(lambda: self.api.dcim.devices.all())

            logger.info(
                "Nautobot: Fetching additional metadata (statuses, namespaces, tags)"
            )
            statuses_task = executor.submit(lambda: self.api.extras.statuses.all())
            global_namespace_task = executor.submit(
                lambda: self.api.ipam.namespaces.get(name="Global")["id"]  # type: ignore
            )
            soft_delete_tag_id_task = executor.submit(
                lambda: self.api.extras.tags.get(name="Soft Delete")["id"]  # type: ignore
            )

            # Now join the threads and get the results
            if "prefixes" in datasets:
                prefixes = list(dict(p) for p in prefixes_task.result())  # type: ignore
            else:
                prefixes = []

            if "addresses" in datasets:
                addresses = list(dict(a) for a in addresses_task.result())  # type: ignore
            else:
                addresses = []

            if "devices" in datasets:
                devices = list(dict(d) for d in devices_task.result())  # type: ignore
            else:
                devices = []

            statuses: dict[str, Status] = {
                s["id"]: s["name"]  # type: ignore
                for s in statuses_task.result()
                if s["name"] in ["Active", "Reserved", "Deprecated"]  # type: ignore
            }  # type: ignore
            global_namespace_id: str = global_namespace_task.result()  # type: ignore
            soft_delete_tag_id: str = soft_delete_tag_id_task.result()  # type: ignore

        return NautobotDataRaw(
            prefixes=prefixes,
            addresses=addresses,
            statuses=statuses,
            devices=devices,
            global_namespace_id=global_namespace_id,
            soft_delete_tag_id=soft_delete_tag_id,
        )

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.create_prefixes(records)  # type: ignore
            elif dataset == "addresses":
                self.create_addresses(records)  # type: ignore
            elif dataset == "devices":
                self.create_devices(records)  # type: ignore

    def create_prefixes(self, prefixes: dict[network_prefix_as_str, PrefixModel]):
        logger.info(f"Nautobot: Creating {len(prefixes)} prefixes")
        for data in prefixes.values():
            payload = dict(
                prefix=data.prefix,
                description=data.description,
                status=data.status,
                type=data.type,
            )
            self.api.ipam.prefixes.create(payload)

    def create_addresses(self, addresses: dict[ip_address_as_str, IPAddressModel]):
        logger.info(f"Nautobot: Creating {len(addresses)} addresses")
        for data in addresses.values():
            payload = dict(
                address=f"{data.address}/{data.prefixlen}",
                description=data.name,
                status=data.status,
                dns_name=data.dns_name,
                namespace=self.syncdata.local_ids["Global namespace"],
            )
            self.api.ipam.ip_addresses.create(payload)

    def create_devices(self, devices: dict[str, DeviceModel]):
        raise NotImplementedError

    def update(self, recordset: dict[DatasetName, dict[CommonID, DatasetUpdate]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.update_prefixes(records)  # type: ignore
            elif dataset == "addresses":
                self.update_addresses(records)  # type: ignore
            elif dataset == "devices":
                self.update_devices(records)  # type: ignore

    def update_prefixes(self, prefixes: dict[network_prefix_as_str, DatasetUpdate]):
        logger.info(f"Nautobot: Updating {len(prefixes)} prefixes")
        for prefix, data in prefixes.items():
            id_ = self.syncdata.local_ids[prefix]
            src_data: PrefixModel = data["source"]  # type: ignore
            payload = dict(
                prefix=src_data.prefix,
                description=src_data.description,
                status=src_data.status,
                type=src_data.type,
            )
            try:
                self.api.ipam.prefixes.update(id_, payload)
            except pynautobot.RequestError as e:
                logger.warning(
                    f"Attempted to update prefix {prefix}, but its id was not found in Nautobot, skipping..."
                )
                logger.debug(f"Error message: {e}")

    def update_addresses(self, addresses: dict[ip_address_as_str, DatasetUpdate]):
        logger.info(f"Nautobot: Updating {len(addresses)} addresses")
        for address, data in addresses.items():
            src_data: IPAddressModel = data["source"]  # type: ignore
            id_ = self.syncdata.local_ids[address]
            payload = dict(
                address=f"{src_data.address}/{src_data.prefixlen}",
                description=src_data.name,
                status=src_data.status,
                dns_name=src_data.dns_name,
                namespace=self.syncdata.local_ids["Global namespace"],
            )
            self.api.ipam.ip_addresses.update(id_, payload)

    def update_devices(self, devices: dict[str, tuple[DeviceModel, DeviceModel]]):
        raise NotImplementedError

    def delete(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        for dataset, records in recordset.items():
            logger.info(f"Nautobot: Deleting {len(records)} {dataset}")
            with cf.ThreadPoolExecutor(
                thread_name_prefix="nautobot_delete"
            ) as executor:
                for record_id in records:
                    executor.submit(self.delete_one, dataset, record_id)

    def delete_one(self, dataset, record):
        soft_delete_tag = dict(id=self.syncdata.local_ids["Soft Delete tag"])
        api_endpoint = self._get_api_endpoint(dataset)
        dataset_singular = dict(prefixes="Prefix", addresses="IP Address")[dataset]
        id_ = self.syncdata.local_ids[record]
        logger.info(f"Nautobot: Soft-deleting {dataset_singular} {record}")

        # get the existing record
        try:
            r = api_endpoint.get(id_)
        except pynautobot.RequestError as e:
            logger.warning(
                f"Attempted to delete record {record}, but its id was not found in Nautobot, skipping..."
            )
            logger.debug(f"Error message: {e}")
            return
        assert isinstance(r, Record), f"Expected a single record, but got a list: {r}"

        # add the soft delete tag to the record's (possibly empty) tags list
        assert isinstance(r.tags, list), f"Expected a list of tags, but got: {r.tags}"
        r.tags.append(soft_delete_tag)

        # update the record with the new tags list
        r.update(dict(tags=r.tags))  # type: ignore

    def _get_api_endpoint(self, dataset) -> pynautobot.core.endpoint.Endpoint:
        endpoint_name = dict(prefixes="prefixes", addresses="ip-addresses")[dataset]
        return getattr(self.api.ipam, endpoint_name)


class NautobotDataRaw(BaseModel):
    prefixes: list[dict]
    addresses: list[dict]
    devices: list[dict]
    statuses: dict[str, Status]  # maps status id to status name
    global_namespace_id: str
    soft_delete_tag_id: str


class BluecatRawData(BaseModel):
    configuration_id: int
    dns_view_id: int
    ip_objects: list[dict]
    dns_objects: list[dict]


class BluecatTarget(Target):
    name = "bluecat"

    def __init__(self) -> None:
        self.api = BluecatSettings.from_cache().get_api_connection(multi_threaded=True)

    def load_data(self, datasets: set[DatasetName]):
        raw_data = self.load_data_raw(datasets)
        objects_by_id = {}
        objects_by_ip = {}
        dns_by_ip = {}
        local_ids = {}
        # construct id lookup table for cross-references
        for ip_object in raw_data.ip_objects:
            objects_by_id[ip_object["id"]] = ip_object
            if ip_object["type"] in ["IP4Address", "IP6Address"]:
                address = ip_object["properties"]["address"]
                objects_by_ip[address] = ip_object
                local_ids[address] = ip_object["id"]

        for dns_object in raw_data.dns_objects:
            objects_by_id[dns_object["id"]] = dns_object
            if dns_object["type"] == "HostRecord":
                _fqdn = dns_object["properties"]["absoluteName"]
                local_ids[_fqdn] = dns_object["id"]
                for ip in dns_object["properties"]["addresses"].split(","):
                    if ip in dns_by_ip:
                        other_fqdn = dns_by_ip[ip]["properties"]["absoluteName"]
                        # In the case of multiple DNS records for the same IP,
                        # we don't really care which DNS record wins and gets incorporated into the syncdata,
                        # so long as the one we choose is consistent.
                        # We'll choose the one with the lexicographically smaller FQDN,
                        # but any consistent choice would work.
                        if other_fqdn < _fqdn:
                            continue
                    dns_by_ip[ip] = dns_object

        prefixes = {}
        addresses = {}

        # Prefixes
        for ip_object in raw_data.ip_objects:
            if ip_object["type"] in ["IP4Block", "IP6Block"]:
                type_ = "container"
            elif ip_object["type"] in ["IP4Network", "IP6Network"]:
                type_ = "network"
            elif ip_object["type"] in ["IP4Address", "IP6Address"]:
                type_ = "address"
            else:
                raise Exception(f"Unexpected object type {ip_object['type']}")

            if prefix := self._get_prefix(ip_object):
                local_ids[prefix] = ip_object["id"]
            elif type_ == "address":
                address = ip_object["properties"]["address"].lower()
            else:
                raise Exception(f"Prefix not found for object {ip_object['id']}")

            # Infer status from name
            _name = ip_object["name"] or ""

            # groups: reserved, deprecated
            pattern = re.compile(
                r"""
                (reserve[d]?|tbd|do-not-use|cannot-use|avoid\ this) # reserved
                |(to-be-moved|remove[d]?|deprecated|old-|unused|replaced|decommissioned|legacy|reclaimed) # deprecated
            """,
                re.VERBOSE | re.IGNORECASE,
            )

            match = pattern.search(_name)
            if match and match.group(1):
                status = "Reserved"
            elif match and match.group(2):
                status = "Deprecated"
            else:
                status = "Active"

            if type_ == "address":
                if "addresses" not in datasets:
                    continue
                if ip_object["properties"]["state"].startswith("DHCP_"):
                    continue  # skip DHCP addresses
                if ip_object["properties"]["state"] == "GATEWAY" and not _name:
                    continue  # skip gateway addresses without a name
                if ip_object["properties"]["state"] not in ["STATIC", "GATEWAY"]:
                    raise Exception(
                        f"Unexpected state {ip_object['properties']['state']} for address {ip_object['id']}"
                    )

                dns_name = dns_by_ip.get(address)
                if dns_name:
                    dns_name = dns_name["properties"]["absoluteName"]
                else:
                    dns_name = ""

                parent = objects_by_id[ip_object["parent_id"]]
                prefix: str | None = self._get_prefix(parent)
                if prefix is None:
                    raise Exception(
                        f"Parent prefix not found for object {ip_object['id']}"
                    )
                pfx_len = prefix.partition("/")[2]
                addresses[address] = IPAddressModel(
                    address=address,
                    prefixlen=pfx_len,
                    name=_name,
                    status=status,
                    dns_name=dns_name,
                )

            else:
                if "prefixes" not in datasets:
                    continue
                pfx = str(IPNetwork(prefix)).lower()
                prefixes[pfx] = PrefixModel(
                    prefix=pfx,
                    description=_name,
                    type=type_,
                    status=status,
                )

        self.syncdata = SyncData(
            prefixes=prefixes, addresses=addresses, local_ids=local_ids, devices=None
        )

    def load_data_raw(self, datasets: set[DatasetName]):
        bc = self.api
        configuration_id = bc.configuration_id
        dns_view_id = bc.get_view()["id"]
        ip_objects, dns_objects = bc.multithread_jobs(
            bc.get_ip_objects, bc.get_dns_objects
        )
        return BluecatRawData(
            configuration_id=configuration_id,
            dns_view_id=dns_view_id,
            ip_objects=ip_objects,
            dns_objects=dns_objects,
        )

    @staticmethod
    def _get_prefix(ip_object):
        if "properties" not in ip_object:
            raise Exception(f"Missing properties for object {ip_object['id']}")
        props = ip_object["properties"]
        if "CIDR" in props:
            return props["CIDR"]
        elif "prefix" in props:
            return props["prefix"]
        else:
            return None

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        created_ids = []
        if "prefixes" in recordset:
            created_ids.extend(self.create_prefixes(recordset["prefixes"]))  # type: ignore
        if "addresses" in recordset:
            created_ids.extend(self.create_addresses(recordset["addresses"]))  # type: ignore
        if "devices" in recordset:
            raise NotImplementedError
        return created_ids

    def create_prefixes(self, prefixes: dict[network_prefix_as_str, PrefixModel]):
        logger.info(f"Bluecat: Creating {len(prefixes)} prefixes")
        created_ids = []

        # create prefixes in order from largest to smallest,
        # so that the parent prefix is created before the child prefix
        prefixes_to_create = sorted(
            [IPNetwork(p) for p in prefixes.keys()], key=lambda x: x.prefixlen
        )
        for net in prefixes_to_create:
            data = prefixes[str(net)]
            new_id = self.create_prefix(net, data)
            created_ids.append(new_id)
            # add the new id to the local_ids table
            self.syncdata.local_ids[data.prefix] = new_id
            # add the new network to the syncdata prefixes dict
            # so it can be looked up and used as a parent_id for a smaller prefix being created at the same time
            assert self.syncdata.prefixes
            self.syncdata.prefixes[data.prefix] = data
        return created_ids

    def create_prefix(self, net: IPNetwork, data: PrefixModel):
        parent_id: int = self.find_parent_id(net)
        name = data.description
        if data.status == "Deprecated":
            name += "-DEPRECATED"
        elif data.status == "Reserved":
            name += "-RESERVED"
        return self.api.create_prefix(
            net=net,
            name=name,
            type=data.type,
            parent_id=parent_id,
        )

    def create_addresses(self, addresses: dict[ip_address_as_str, IPAddressModel]):
        return []

    def find_parent_id(self, this_net: IPNetwork) -> int:
        "Find the smallest parent prefix that contains the given prefix"
        v4_nets, v6_nets = self.all_nets()
        if this_net.version == 4:
            nets = v4_nets
        else:
            nets = v6_nets
        # nets are already sorted from smallest to largest, so first hit should be the parent
        for net in nets:
            if this_net in net:
                # uppercase prefix in local_ids because bluecat returns IPv6 addresses uppercased
                return self.syncdata.local_ids[str(net).upper()]  # type: ignore
        raise Exception(f"Parent prefix not found for {this_net}")

    def all_nets(self):
        self._ipv4_nets = []
        self._ipv6_nets = []
        assert self.syncdata.prefixes, "Prefixes must be loaded before calling all_nets"
        for pfx in self.syncdata.prefixes.keys():
            net = IPNetwork(pfx)
            if net.version == 4:
                self._ipv4_nets.append(net)
            else:
                self._ipv6_nets.append(net)
        self._ipv4_nets.sort(key=lambda x: x.prefixlen, reverse=True)
        self._ipv6_nets.sort(key=lambda x: x.prefixlen, reverse=True)
        return self._ipv4_nets, self._ipv6_nets
