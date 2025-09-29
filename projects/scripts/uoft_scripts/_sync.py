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

from functools import cached_property
import typing as t
import threading
import re
import concurrent.futures as cf

from uoft_core.api import RESTAPIError
from uoft_core.types import IPNetwork, BaseModel, Field
from uoft_core.prompt import Prompt
from uoft_bluecat import Settings as BluecatSettings
from uoft_librenms import Settings as LibrenmsSettings
from uoft_core import logging

import pynautobot
import pynautobot.core.endpoint
from pynautobot.core.response import Record
import requests
import deepdiff
import deepdiff.model
import typer

from .nautobot import get_settings


logger = logging.getLogger(__name__)

app = typer.Typer(name="nautobot")

ip_address_as_str: t.TypeAlias = str
"ip address, e.g. '192.168.0.20'"
network_prefix_as_str: t.TypeAlias = str
"network prefix in CIDR notation, e.g. '10.0.0.0/8'"
CommonID: t.TypeAlias = ip_address_as_str | network_prefix_as_str
"common id used to identify objects in both systems"

# The `| str` here is a catchall for any undefined status pulled from nautobot
Status: t.TypeAlias = t.Literal["Active", "Reserved", "Deprecated", "Planned"] | str

PrefixType: t.TypeAlias = t.Literal["container", "network", "pool"]

OnOrphanAction: t.TypeAlias = t.Literal["prompt", "delete", "backport", "skip"]


class IPAddressModel(BaseModel):
    address: str
    prefixlen: int
    name: str
    status: Status
    dns_name: str

    @cached_property
    def _interface(self):
        return IPNetwork(f"{self.address}/{self.prefixlen}")

    @property
    def interface(self):
        """
        Returns the CIDR of this address as an IPNetwork object.
        This is a cached property to avoid recalculating it multiple times.
        """
        return self._interface


class PrefixModel(BaseModel):
    prefix: network_prefix_as_str
    description: str
    type: PrefixType
    status: Status

    @cached_property
    def _ip_network(self):
        return IPNetwork(self.prefix)

    @property
    def ip_network(self) -> IPNetwork:
        """
        Returns the IPNetwork object for this prefix.
        This is a cached property to avoid recalculating it multiple times.
        """
        return self._ip_network


class DeviceModel(BaseModel):
    hostname: str
    ip_address: ip_address_as_str
    status: Status | None = None


Prefixes: t.TypeAlias = dict[network_prefix_as_str, PrefixModel]
Addresses: t.TypeAlias = dict[ip_address_as_str, IPAddressModel]
Devices: t.TypeAlias = dict[str, DeviceModel]
DatasetName: t.TypeAlias = t.Literal["prefixes", "addresses", "devices"]


# models come from source and dest
class DatasetUpdate(t.TypedDict):
    source: BaseModel
    dest: BaseModel


class Changes(BaseModel):
    # model comes from source
    create: dict[DatasetName, dict[CommonID, BaseModel]] = Field(default_factory=dict)

    update: dict[DatasetName, dict[CommonID, DatasetUpdate]] = Field(default_factory=dict)

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

    def preprocess(self, source: str | None = None, dest: str | None = None):
        pass

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        raise NotImplementedError

    def update(self, recordset: dict[DatasetName, dict[CommonID, DatasetUpdate]]):
        raise NotImplementedError

    def delete(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
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
        self.diff = None  # pyright: ignore[reportAttributeAccessIssue]
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

    def preprocess(self):
        """
        Pre-process / transform the data before synchronization.
        This method dispatches out to the preprocess methods of the source and destination systems.
        """
        logger.info("Giving each side of the sync a chance to preprocess the data it will present")
        self.source.preprocess(dest=self.dest.name)
        self.dest.preprocess(source=self.source.name)

    def synchronize(self):
        assert self.loaded, "Data must be loaded before synchronization can occur"
        self.preprocess()

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
                    self.changes.create.setdefault(dataset, {})[common_id] = source_record
                elif source_record != dest_record:
                    self.changes.update.setdefault(dataset, {})[common_id] = dict(  # pyright: ignore[reportArgumentType]
                        source=source_record,
                        dest=dest_record,
                    )
            for common_id, dest_record in dest_data.items():
                if common_id not in source_data:
                    self.changes.delete.setdefault(dataset, {})[common_id] = dest_record
        logger.info("Data comparison complete")

        records_to_create = ", ".join([f"{len(records)} {dataset}" for dataset, records in self.changes.create.items()])
        records_to_update = ", ".join([f"{len(records)} {dataset}" for dataset, records in self.changes.update.items()])
        orphaned_records = ", ".join([
            f"{len(records)} orphaned {dataset}" for dataset, records in self.changes.delete.items()
        ])
        records_to_create = f"{records_to_create} to create" if records_to_create else ""
        records_to_update = f"{records_to_update} to update" if records_to_update else ""
        orphaned_records = (
            f"{orphaned_records} (records that exist in the destination system, but not in the source system)"
            if orphaned_records
            else ""
        )
        total_records = ', '.join(filter(lambda x: x, [records_to_create, records_to_update, orphaned_records]))
        msg = f"Found {total_records}" if total_records else "No records to synchronize, everything is in sync!"
        logger.info(msg)

    def commit(self):
        assert self.changes is not None, "Synchronize must be called before commit"
        self.dest.create(self.changes.create)
        self.dest.update(recordset=self.changes.update)

        if self.changes.delete:
            self._handle_orphaned_records()

    def _handle_orphaned_records(self):
        orphaned_records = [f"{len(records)} {dataset}" for dataset, records in self.changes.delete.items() if records]
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
        settings = get_settings(dev)
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
            self._local_ns.api = pynautobot.api(self.url, token=self.token.get_secret_value())
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
            if nb_prefix["tags"] and raw_data.soft_delete_tag_id in [t["id"] for t in nb_prefix["tags"]]:
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
            if nb_address["tags"] and raw_data.soft_delete_tag_id in [t["id"] for t in nb_address["tags"]]:
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
            device_status = raw_data.statuses[nb_device["status"]["id"]]
            if ip4 := nb_device.get("primary_ip4"):
                ip_addr_id = ip4["id"]
            elif ip6 := nb_device.get("primary_ip6"):
                ip_addr_id = ip6["id"]
            elif device_status != "Active":
                logger.warning(
                    f"Nautobot: Device {nb_device['name']} is not active and "
                    "does not have an IP address, skipping..."
                )
                continue
            else:
                raise Exception(f"Device {nb_device['name']} has no primary IP address")
            ip_address = self.api.ipam.ip_addresses.get(ip_addr_id)
            ip_address = t.cast(Record, ip_address)
            ip_address = ip_address["address"]
            devices[nb_device["name"]] = dict(hostname=nb_device["name"], ip_address=ip_address, status=device_status)

        self.syncdata = SyncData(
            prefixes=prefixes or None,
            addresses=addresses or None,
            devices=devices or None,
            local_ids=local_ids,
        )

    def load_data_raw(self, datasets: set[DatasetName]):
        with cf.ThreadPoolExecutor(thread_name_prefix="nautobot_fetch_data") as executor:
            if "prefixes" in datasets:
                logger.info("Nautobot: Fetching all Prefixes")
                prefixes_task = executor.submit(lambda: self.api.ipam.prefixes.all())

            if "addresses" in datasets:
                logger.info("Nautobot: Fetching all IP Addresses")
                addresses_task = executor.submit(lambda: self.api.ipam.ip_addresses.all())

            if "devices" in datasets:
                logger.info("Nautobot: Fetching all Devices")
                devices_task = executor.submit(lambda: self.api.dcim.devices.all())

            logger.info("Nautobot: Fetching additional metadata (statuses, namespaces, tags)")
            statuses_task = executor.submit(lambda: self.api.extras.statuses.all())
            global_namespace_task = executor.submit(
                lambda: t.cast(str, t.cast(Record, self.api.ipam.namespaces.get(name="Global"))["id"])
            )
            soft_delete_tag_id_task = executor.submit(
                lambda: t.cast(str, t.cast(Record, self.api.extras.tags.get(name="Soft Delete"))["id"])
            )

            # Now join the threads and get the results
            if "prefixes" in datasets:
                prefixes = list(dict(p) for p in t.cast(list[Record], prefixes_task.result()))  # pyright: ignore[reportPossiblyUnboundVariable]
            else:
                prefixes = []

            if "addresses" in datasets:
                addresses = list(dict(a) for a in t.cast(list[Record], addresses_task.result()))  # pyright: ignore[reportPossiblyUnboundVariable]
            else:
                addresses = []

            if "devices" in datasets:
                devices = list(dict(d) for d in t.cast(list[Record], devices_task.result()))  # pyright: ignore[reportPossiblyUnboundVariable]
            else:
                devices = []

            statuses: dict[str, Status] = {
                t.cast(str, s["id"]): t.cast(Status, s["name"]) for s in t.cast(list[Record], statuses_task.result())
            }
            global_namespace_id = global_namespace_task.result()
            soft_delete_tag_id = soft_delete_tag_id_task.result()

        return NautobotDataRaw(
            prefixes=prefixes,
            addresses=addresses,
            statuses=statuses,
            devices=devices,
            global_namespace_id=global_namespace_id,
            soft_delete_tag_id=soft_delete_tag_id,
        )

    def preprocess(self, source: str | None = None, dest: str | None = None):
        if source is None:
            if dest == "librenms":
                # strip the netmask from all device ip addresses
                assert self.syncdata.devices
                filtered_devices = {}
                for device_name, device in self.syncdata.devices.items():
                    if device.status and device.status != "Active":
                        continue
                    device.ip_address = device.ip_address.split("/")[0]
                    # strip the status from all devices. we no longer need it
                    device.status = None
                    filtered_devices[device_name] = device
                self.syncdata.devices = filtered_devices
            elif self.syncdata.devices:
                for device in self.syncdata.devices.values():
                    device.status = None

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.create_prefixes(records)  # pyright: ignore[reportArgumentType]
            elif dataset == "addresses":
                self.create_addresses(records)  # pyright: ignore[reportArgumentType]
            elif dataset == "devices":
                self.create_devices(records)  # pyright: ignore[reportArgumentType]

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
            try:
                self.api.ipam.ip_addresses.create(payload)
            except pynautobot.RequestError as e:
                if e.req.status_code == 400 and "already exists" in e.error:
                    logger.warning(f"Attempted to create address {data.address}, but it already exists, skipping...")
                else:
                    raise

    def create_devices(self, devices: dict[str, DeviceModel]):
        raise NotImplementedError

    def update(self, recordset: dict[DatasetName, dict[CommonID, DatasetUpdate]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.update_prefixes(records)
            elif dataset == "addresses":
                self.update_addresses(records)
            elif dataset == "devices":
                self.update_devices(records)  # pyright: ignore[reportArgumentType]

    def update_prefixes(self, prefixes: dict[network_prefix_as_str, DatasetUpdate]):
        logger.info(f"Nautobot: Updating {len(prefixes)} prefixes")
        for prefix, data in prefixes.items():
            id_ = self.syncdata.local_ids[prefix]
            src_data = t.cast(PrefixModel, data["source"])
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
            src_data = t.cast(IPAddressModel, data["source"])
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
            with cf.ThreadPoolExecutor(thread_name_prefix="nautobot_delete") as executor:
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
            logger.warning(f"Attempted to delete record {record}, but its id was not found in Nautobot, skipping...")
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
    blocks: list[dict]
    nets: list[dict]
    addrs: list[dict]


class BluecatTarget(Target):
    name = "bluecat"

    def __init__(self, configuration=None) -> None:
        self.configuration = configuration or "UTSCProduction"
        self.api = BluecatSettings.from_cache().get_api_connection(configuration)
        self.api.login()

    @cached_property
    def _status_pattern(self):
        # groups: reserved, deprecated
        pattern = re.compile(
            r"""
            (reserve[d]?|tbd|do-not-use|cannot-use|avoid\ this) # reserved
            |(to-be-moved|remove[d]?|deprecated|old-|unused|replaced|decommissioned|legacy|reclaimed) # deprecated
        """,
            re.VERBOSE | re.IGNORECASE,
        )
        return pattern

    def _infer_status(self, name):
        match = self._status_pattern.search(name)
        if match and match.group(1):
            status = "Reserved"
        elif match and match.group(2):
            status = "Deprecated"
        else:
            status = "Active"
        return status

    def _is_gateway(self, addr: IPAddressModel) -> bool:
        if addr.interface.version == 6:
            return False
        if addr.prefixlen > 30:
            # /31s do not have gateway addresses in bluecat
            return False
        return addr.interface.ip == addr.interface.network + 1

    def _name_missing_status_indicator(self, name: str) -> bool:
        """
        Check if the name needs a suffix to denote the object's status.
        This is used to determine if we need to append "-DEPRECATED" or "-RESERVED"
        to the name when creating an address.
        """
        # Bluecat does not have a "deprecated" state for addresses or prefixes,
        # so we parse the name to check if it contains any keywords that indicate
        # that the address or prefix is deprecated, and when writing objects back to bluecat,
        # we append "-DEPRECATED" to the name, but only if the object name doesn't already contain
        # a deprecation indicator.
        return self._status_pattern.search(name) is None

    def load_data(self, datasets: set[DatasetName]):
        raw_data = self.load_data_raw(datasets)
        objects_by_id = {}
        objects_by_ip = {}
        local_ids = {}

        if "prefixes" in datasets:
            prefixes = self._load_prefixes(raw_data, objects_by_id, objects_by_ip, local_ids)
        else:
            prefixes = {}

        if "addresses" in datasets:
            addresses = self._load_addresses(raw_data, objects_by_id, objects_by_ip, local_ids)
        else:
            addresses = {}

        self.syncdata = SyncData(prefixes=prefixes, addresses=addresses, local_ids=local_ids, devices=None)

    def _load_prefixes(self, raw_data, objects_by_id, objects_by_ip, local_ids):
        prefixes = {}
        for raw_net in raw_data.blocks + raw_data.nets:
            raw_id = raw_net["id"]
            objects_by_id[raw_id] = raw_net
            if raw_net["type"] in ["IPv4Block", "IPv6Block"]:
                type_ = "container"
            elif raw_net["type"] in ["IPv4Network", "IPv6Network"]:
                type_ = "network"
            else:
                raise Exception(f"Unexpected object type {raw_net['type']}")
            name = raw_net["name"] or ""
            status = self._infer_status(name)
            prefix: str = raw_net["range"]  # type: ignore
            # Bluecat sometimes returns ip addresses and prefixes in lowercase, sometimes in uppercase,
            # so we normalize them to lowercase for consistency
            prefix = prefix.lower()

            objects_by_ip[prefix] = raw_net
            local_ids[prefix] = raw_net["id"]
            prefixes[prefix] = PrefixModel(
                prefix=prefix,
                description=name,
                type=type_,
                status=status,
            )
        return prefixes

    def _load_addresses(self, raw_data, objects_by_id, objects_by_ip, local_ids):
        addresses = {}
        for raw_net in raw_data.blocks + raw_data.nets:
            # make sure all prefixes are indexable by id, even if "prefixes" is not in datasets
            objects_by_id[raw_net["id"]] = raw_net

        for raw_addr in raw_data.addrs:
            name = raw_addr["name"] or ""
            raw_id = raw_addr["id"]
            objects_by_id[raw_id] = raw_addr
            address = raw_addr["address"]
            # Bluecat sometimes returns ip addresses and prefixes in lowercase, sometimes in uppercase,
            # so we normalize them to lowercase for consistency
            address = address.lower()
            objects_by_ip[address] = raw_addr
            local_ids[address] = raw_addr["id"]

            parent_id = raw_addr["_links"]["up"]["href"].split("/")[-1]
            parent_prefix = objects_by_id[int(parent_id)]["range"]
            pfx_len = parent_prefix.partition("/")[2]

            rrs = raw_addr["_embedded"]["resourceRecords"]
            dns_name = rrs[0]["absoluteName"] if rrs else ""

            status = self._infer_status(name)

            addresses[address] = IPAddressModel(
                address=address,
                prefixlen=pfx_len,
                name=name,
                status=status,
                dns_name=dns_name,
            )
        return addresses

    def load_data_raw(self, datasets: set[DatasetName]):
        with logging.Context(f"Bluecat-{self.configuration}"):
            if "prefixes" in datasets or "addresses" in datasets:
                # prefix data is needed to find parent prefixes for addresses
                blocks = self.api.get_all("/blocks")
                nets = self.api.get_all("/networks")
            else:
                blocks = []
                nets = []
            if "addresses" in datasets:
                # skip DHCP addresses, cuts the resulting data from >130k records down to ~6k records
                addrs = self.api.get_all(
                    "/addresses", params=dict(filter="state:in('GATEWAY', 'STATIC')", fields="embed(resourceRecords)")
                )
            else:
                addrs = []
        return BluecatRawData(
            blocks=blocks,
            nets=nets,
            addrs=addrs,
        )

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        created_ids = []
        if "prefixes" in recordset:
            created_ids.extend(self.create_prefixes(recordset["prefixes"]))  # pyright: ignore[reportArgumentType]
        if "addresses" in recordset:
            created_ids.extend(self.create_addresses(recordset["addresses"]))  # pyright: ignore[reportArgumentType]
        if "devices" in recordset:
            raise NotImplementedError
        return created_ids

    def create_prefixes(self, prefixes: dict[network_prefix_as_str, PrefixModel]):
        logger.info(f"Bluecat: Creating {len(prefixes)} prefixes")
        created_ids = []

        # create prefixes in order from largest to smallest,
        # so that the parent prefix is created before the child prefix
        prefixes_to_create = sorted([p for p in prefixes.values()], key=lambda x: x.ip_network.prefixlen)
        for pfx in prefixes_to_create:
            res = self.create_prefix(pfx)
            new_id = res["id"]
            created_ids.append(new_id)
            # add the new id to the local_ids table
            self.syncdata.local_ids[pfx.prefix] = new_id
            # add the new network to the syncdata prefixes dict
            # so it can be looked up and used as a parent_id for a smaller prefix being created at the same time
            assert self.syncdata.prefixes
            self.syncdata.prefixes[pfx.prefix] = pfx
        return created_ids

    def create_prefix(self, pfx: PrefixModel):
        parent_id: int = self._find_parent_id(pfx.ip_network)
        name = pfx.description
        if pfx.status == "Deprecated" and self._name_missing_status_indicator(name):
            name += "-DEPRECATED"
        elif pfx.status == "Reserved" and self._name_missing_status_indicator(name):
            name += "-RESERVED"
        logger.info(f"Creating prefix {pfx.prefix} with name {name}")
        if pfx.type == "container":
            return self.api.create_block(
                range=pfx.ip_network,
                name=name,
                parent_id=parent_id,
            )
        elif pfx.type == "network":
            return self.api.create_network(
                range=pfx.ip_network,
                name=name,
                parent_id=parent_id,
            )
        else:
            raise NotImplementedError("TODO: add support for pools / ip ranges")

    def create_addresses(self, addresses: dict[ip_address_as_str, IPAddressModel]):
        created_ids = []
        for addr in addresses.values():
            res = self.create_address(addr)
            new_id = res["id"]
            created_ids.append(new_id)
        return created_ids

    def create_address(self, addr: IPAddressModel):
        state = "STATIC"
        name = addr.name
        if self._is_gateway(addr):
            state = "GATEWAY"
        elif addr.status == "Reserved" and self._name_missing_status_indicator(name):
            state = "RESERVED"
        elif addr.status == "Deprecated" and self._name_missing_status_indicator(name):
            name += "-DEPRECATED"

        # create the address in Bluecat
        logger.info(f"Creating address {addr.address} with name {name} and state {state}")
        address = self.api.create_address(
            address=addr.interface.ip,
            name=name,
            state=state,
        )
        if addr.dns_name:
            self.create_or_update_host_record(addr, address["id"])
        return address

    def create_or_update_host_record(self, addr: IPAddressModel, ip_address_id: int):
        """
        Create or update a host record in Bluecat for the given DNS name and address ID.
        If the host record already exists, it will be updated to include the new address.
        """
        assert "." in addr.dns_name, f"{addr}: DNS name must be a fully qualified domain name"
        dns_host, _, dns_zone = addr.dns_name.partition(".")
        logger.info(f"Creating address {addr.address} with name {dns_host} in zone {dns_zone}")
        zone = self.api.get("/zones", params=dict(filter=f"absoluteName:eq('{dns_zone}')")).json()["data"]
        if len(zone) == 0:
            logger.warning(f"Zone '{dns_zone}' not found. Creating it now.")
            zone = self.api.create_zone(dns_zone)
        else:
            zone = zone[0]
        try:
            self.api.create_host_record(dns_host, ip_address_id, zone["id"])
        except RESTAPIError as e:
            if e.data and "code" in e.data and e.data["code"] == "ResourceAlreadyExists":
                logger.warning(
                    f"Host record {dns_host} already exists in zone {dns_zone}, adding {addr.address} to it..."
                )
                host = self.api.get_host_record(addr.dns_name, params=dict(fields="embed(addresses)"))
                addresses = host.pop("_embedded", {}).get("addresses", [])
                addresses.append({"id": ip_address_id})
                host["addresses"] = addresses
                self.api.update_host_record(host["id"], host)
            else:
                logger.error(f"Failed to create host record {dns_host} in zone {dns_zone}: {e}")
                raise e

    def remove_address_from_host_record(self, host_record_name: str, address_id: int, addr_info: IPNetwork):
        host = self.api.get_host_record(absolute_name=host_record_name, params=dict(fields="embed(addresses)"))
        addresses = host.pop("_embedded", {}).get("addresses", [])
        if len(addresses) > 1:
            # remove this address from the host record
            logger.info(f"Removing address {addr_info.ip} from DNS record {host_record_name}")
            for entry in addresses.copy():
                if entry["id"] == address_id:
                    addresses.remove(entry)
            host["addresses"] = addresses
            self.api.update_host_record(host["id"], host)
        else:
            # if this is the only address in the host record, delete the host record
            logger.warning(f"Deleting old DNS record {host_record_name} for address {addr_info.ip}")
            self.api.delete_host_record(host["id"])

    def update(self, recordset: dict[DatasetName, dict[CommonID, DatasetUpdate]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.update_prefixes(records)
            elif dataset == "addresses":
                self.update_addresses(records)

    def update_prefixes(self, prefixes: dict[network_prefix_as_str, DatasetUpdate]):
        logger.info(f"Bluecat: Updating {len(prefixes)} prefixes")
        for record in prefixes.values():
            src_pfx = t.cast(PrefixModel, record["source"])
            dest_pfx = t.cast(PrefixModel, record["dest"])
            id_ = t.cast(int, self.syncdata.local_ids[dest_pfx.prefix])
            ip_network = src_pfx.ip_network

            name = src_pfx.description
            if src_pfx.status == "Deprecated" and self._name_missing_status_indicator(name):
                # bluecat does not have a "deprecated" state, so we append "-DEPRECATED
                name += "-DEPRECATED"
            elif src_pfx.status == "Reserved" and self._name_missing_status_indicator(name):
                # bluecat does not have a "reserved" state for prefixes, so we append "-RESERVED
                name += "-RESERVED"

            if src_pfx.type != dest_pfx.type:
                logger.warning(
                    f"Prefix {ip_network} type changed from {dest_pfx.type} to {src_pfx.type}, "
                    "this is not supported, skipping update"
                )
                continue
            if src_pfx.type == "container":
                type_ = "IPv4Block" if ip_network.version == 4 else "IPv6Block"
                logger.info(f"Bluecat: Updating block {ip_network} ({type_}) to {name}")
                self.api.update_block(id_, {"name": name, "range": src_pfx.prefix, "type": type_})
            elif src_pfx.type == "network":
                type_ = "IPv4Network" if ip_network.version == 4 else "IPv6Network"
                logger.info(f"Bluecat: Updating network {ip_network} ({type_}) to {name}")
                self.api.update_network(id_, {"name": name, "range": src_pfx.prefix, "type": type_})
            else:
                raise NotImplementedError("TODO: add support for pools / ip ranges")

    def update_addresses(self, addresses: dict[ip_address_as_str, DatasetUpdate]):
        logger.info(f"Bluecat: Updating {len(addresses)} addresses")
        for record in addresses.values():
            src_addr = t.cast(IPAddressModel, record["source"])
            dest_addr = t.cast(IPAddressModel, record["dest"])
            id_ = t.cast(int, self.syncdata.local_ids[dest_addr.address])

            interface = src_addr.interface
            name = src_addr.name
            state = "STATIC"
            # if address is the first address in a prefix, it is a gateway address
            if interface.ip == interface.network + 1:
                state = "GATEWAY"
            elif src_addr.status == "Reserved":
                state = "RESERVED"
            elif src_addr.status == "Deprecated" and self._name_missing_status_indicator(name):
                # bluecat does not have a "deprecated" state, so we append "-DEPRECATED" to the name
                name += "-DEPRECATED"

            if src_addr.dns_name != dest_addr.dns_name:
                if dest_addr.dns_name:
                    self.remove_address_from_host_record(
                        host_record_name=dest_addr.dns_name, address_id=id_, addr_info=interface
                    )
                if src_addr.dns_name:
                    # if dns record with this name already exists, add this address to it
                    self.create_or_update_host_record(src_addr, id_)
            logger.info(f"Bluecat: Updating address {src_addr.address} ({src_addr.status}) to {name} ({state})")
            self.api.update_address(id_, name, state=state)

    def delete(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        for dataset, records in recordset.items():
            if dataset == "prefixes":
                self.delete_prefixes(records)  # pyright: ignore[reportArgumentType]
            elif dataset == "addresses":
                self.delete_addresses(records)  # pyright: ignore[reportArgumentType]

    def delete_prefixes(self, prefixes: dict[network_prefix_as_str, PrefixModel]):
        logger.info(f"Bluecat: Deleting {len(prefixes)} prefixes")
        # sort prefixes by prefix length, from highest to lowest,
        # so that we delete child prefixes before parent prefixes
        for pfx in sorted(prefixes.values(), key= lambda x: x.ip_network.prefixlen, reverse=True):
            id_ = self.syncdata.local_ids[pfx.prefix]
            msg = f"Deleting prefix {pfx.prefix} ({pfx.type})"
            logger.info(f"Bluecat: {msg}")
            url = f"/blocks/{id_}" if pfx.type == "container" else f"/networks/{id_}"
            self.api.delete(url, comment=msg)

    def delete_addresses(self, addresses: dict[ip_address_as_str, IPAddressModel]):
        logger.warning(f"Bluecat: Deleting {len(addresses)} addresses")
        for addr in addresses.values():
            id_ = self.syncdata.local_ids[addr.address]
            msg = f"Deleting address {addr.address}"
            logger.info(f"Bluecat: {msg}")
            self.api.delete(f"/addresses/{id_}", comment=msg)

    def _find_parent_id(self, this_net: IPNetwork) -> int:
        "Find the smallest parent prefix that contains the given prefix"
        v4_nets, v6_nets = self.all_nets()
        if this_net.version == 4:
            nets = v4_nets
        else:
            nets = v6_nets
        # nets are already sorted from smallest to largest, so first hit should be the parent
        for net in nets:
            if this_net in net:
                # WARNING: at some point, bluecat was returning IPv6 addresses in all uppercase
                # and at some point it started returning them in lowercase. I have no idea why.
                # so we need to normalize the address to lowercase before looking it up in local_ids
                net = str(net).lower()
                return t.cast(int, self.syncdata.local_ids[str(net)])
        logger.warning(f"Parent prefix not found for {this_net}, using configuration root")
        return self.api.configuration_id

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


class LibreNMSTarget(Target):
    name = "librenms"

    def __init__(self) -> None:
        self.api = LibrenmsSettings.from_cache().api_connection()

    def load_data(self, datasets: set[DatasetName]):
        raw_data = self.load_data_raw()

        local_ids = {}
        devices = {}

        logger.info("LibreNMS: Processing devices")
        for raw_device in raw_data:
            # we only care about switches. ignore everything else
            # TODO: add PDUs and UPSes to nautobot, sync to/from librenms
            if raw_device["type"] not in ["network"]:
                continue
            hostname = raw_device["hostname"].split(".")[0]
            local_ids[hostname] = raw_device["device_id"]
            ip_address = raw_device["ip"]
            devices[hostname] = DeviceModel(hostname=hostname, ip_address=ip_address)

        self.syncdata = SyncData(
            prefixes=None,
            addresses=None,
            devices=devices,
            local_ids=local_ids,
        )

    def load_data_raw(self):
        logger.info("LibreNMS: Loading all devices")
        return self.api.devices.list_devices(order_type="all")["devices"]

    def create(self, recordset: dict[DatasetName, dict[CommonID, BaseModel]]):
        devices = recordset["devices"]
        logger.info(f"LibreNMS: Creating {len(devices)} devices")
        for device in devices.values():
            self.create_device(device)  # pyright: ignore[reportArgumentType]

    def create_device(self, device: DeviceModel):
        self.api.devices.add_device(
            hostname=f"{device.hostname}.netmgmt.utsc.utoronto.ca", overwrite_ip=device.ip_address
        )


def _debug():
    sm = SyncManager(NautobotTarget(), BluecatTarget(), {"prefixes", "addresses"}, on_orphan="delete")  # pyright: ignore[reportArgumentType]

    sm.load()
    sm.synchronize()
    sm.commit()
    print("Done!")
