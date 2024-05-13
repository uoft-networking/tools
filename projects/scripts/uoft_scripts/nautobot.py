"""
so it goes like this:

this module has three main classes: 

the base SyncManager class contains the main synchronization logic, 
and is subclassed by the BluecatManager and NautobotManager classes.

each subclass is responsible for loading data from the respective systems, 
and for creating, updating, and deleting objects in the destination system.

the core approach to synchronization is to initialize one instance of each subclass, 
and then call the synchronize method on the destination manager instance, 
passing the source manager instance as an argument.

Full two-way synchronization is done by loading data from both systems,
calling the synchronize method on the destination manager instance,
and then calling the synchronize method on the source manager instance.


"""

import json
import logging
import re
from pathlib import Path
import typing
import threading
import concurrent.futures as cf

from uoft_core.types import IPNetwork, IPAddress, BaseModel, SecretStr
from uoft_core import BaseSettings, Field
from uoft_bluecat import Settings as BluecatSettings

import pynautobot
import pynautobot.core.endpoint
from pynautobot.core.response import Record
import requests
import deepdiff
import deepdiff.model
import typer
import jinja2


class Settings(BaseSettings):
    """Settings for the nautobot_cli application."""

    url: str = Field(..., title="Nautobot server URL")
    token: SecretStr = Field(..., title="Nautobot API Token")

    class Config(BaseSettings.Config):
        app_name = "nautobot-cli"


class DevSettings(Settings):

    class Config(BaseSettings.Config):
        app_name = "nautobot-cli-dev"


logger = logging.getLogger(__name__)

app = typer.Typer(name="nautobot")

ip_address: typing.TypeAlias = str
"ip address in string format, e.g. '192.168.0.20'"
network_prefix: typing.TypeAlias = str
"network prefix in CIDR notation, e.g. '10.0.0.0/8'"
common_id: typing.TypeAlias = ip_address | network_prefix
"common id used to identify objects in both systems"

Status: typing.TypeAlias = typing.Literal["Active", "Reserved", "Deprecated"]
PrefixType: typing.TypeAlias = typing.Literal["container", "network", "pool"]


class IPAddressModel(BaseModel):
    address: ip_address
    name: str
    status: Status
    dns_name: str


class PrefixModel(BaseModel):
    prefix: network_prefix
    description: str
    type: PrefixType
    status: Status


class SyncData(BaseModel):
    prefixes: dict[
        network_prefix, PrefixModel
    ]  # keys are network prefixes in CIDR notation
    addresses: dict[ip_address, IPAddressModel]  # keys are ip addresses

    # the keys will be ip addresses / network cidrs / dns names, and
    # the values will be bluecat object ids or nautobot uuids
    local_ids: dict[common_id, int | str]


class BluecatDataRaw(BaseModel):
    configuration_id: int
    dns_view_id: int
    ip_objects: list[dict]
    dns_objects: list[dict]


class NautobotDataRaw(BaseModel):
    prefixes: list[dict]
    addresses: list[dict]
    statuses: dict[str, Status]  # maps status id to status name
    global_namespace_id: str
    soft_delete_tag_id: str


class SyncManager:
    syncdata: SyncData
    diff: deepdiff.DeepDiff

    def __init__(self) -> None:
        self.syncdata = None  # type: ignore
        self.diff = None  # type: ignore

    def load_data(self):
        raise NotImplementedError

    def create(self):
        raise NotImplementedError

    def update(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def synchronize(self, source_data: SyncData):
        diff = deepdiff.DeepDiff(
            self.syncdata,
            source_data,
            exclude_paths="root.local_ids",
            ignore_order=True,
            report_repetition=True,
            log_frequency_in_sec=1,
        )

        expected_diff_types = {
            "values_changed",
            "dictionary_item_added",
            "dictionary_item_removed",
        }
        assert (
            set(diff.keys()) <= expected_diff_types
        ), f"Deepdiff has identified unexpected type[s] of change: {set(diff.keys()) - expected_diff_types}"

        delta = deepdiff.Delta(diff)

        new_syncdata: SyncData = self.syncdata + delta  # type: ignore

        self.syncdata = new_syncdata
        self.diff = diff

    def save_data(self):
        # all these methods make use of the diff attribute to determine
        # which records need to be created, updated, or deleted
        assert (
            self.diff is not None
        ), "You need to call synchronize() before calling commit()"

        self.create()
        self.update()
        self.delete()

    def _get_all_change_paths(self, change_type):
        # dictionary_item_removed are items not present in source
        # dictionary_item_added are items not present in dest
        # values_changed are individual fields which have changed
        # In order to commit the updated dataset to the destination system,
        # we need to know which entries have been added, which have been removed, and which have been updated
        change_type_mapping = {
            "create": "dictionary_item_added",
            "update": "values_changed",
            "delete": "dictionary_item_removed",
        }
        change_type_name = change_type_mapping[change_type]
        res: dict[str, set[common_id]]
        res = dict(prefixes=set(), addresses=set())
        for record in self.diff.tree[change_type_name]:  # type: ignore
            record: deepdiff.model.DiffLevel
            path: list[str] = record.path(output_format="list")  # type: ignore

            # path lists for records added / removed look like
            # ["prefixes", "10.0.0.0/8"] or ["addresses", "192.168.0.20"],
            # path lists for records updated look like
            # ["prefixes", "10.0.0.0/8", "name"] or ["addresses", "192.168.0.20", "dns_name"]
            dataset_name = path[0]
            record_name = path[1]
            res[dataset_name].add(record_name)
        return res


class NautobotManager(SyncManager):

    def __init__(self, dev=False) -> None:
        super().__init__()
        if dev:
            settings = DevSettings.from_cache()
        else:
            settings = Settings.from_cache()
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

    def load_data(self):
        raw_data = self.load_data_raw()
        logger.info("Nautobot: Parsing and processing data")
        prefixes = {}
        addresses = {}
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
            pfx = str(IPNetwork(nb_prefix["prefix"]))
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
            addr = str(IPAddress(nb_address["host"]))
            status_id = nb_address["status"]["id"]
            local_ids[addr] = nb_address["id"]
            addresses[addr] = IPAddressModel(
                address=addr,
                name=nb_address["description"],
                status=raw_data.statuses[status_id],
                dns_name=nb_address["dns_name"],
            )

        self.syncdata = SyncData(
            prefixes=prefixes,
            addresses=addresses,
            local_ids=local_ids,
        )

    def load_data_raw(self):
        with cf.ThreadPoolExecutor(
            thread_name_prefix="nautobot_fetch_data"
        ) as executor:

            logger.info("Nautobot: Fetching all Prefixes")
            prefixes_task = executor.submit(lambda: self.api.ipam.prefixes.all())

            logger.info("Nautobot: Fetching all IP Addresses")
            addresses_task = executor.submit(lambda: self.api.ipam.ip_addresses.all())

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
            prefixes = list(dict(p) for p in prefixes_task.result())  # type: ignore
            addresses = list(dict(a) for a in addresses_task.result())  # type: ignore
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
            global_namespace_id=global_namespace_id,
            soft_delete_tag_id=soft_delete_tag_id,
        )

    def create(self):
        prefixes = []
        addresses = []
        for dataset, records in self._get_all_change_paths("create").items():
            if dataset == "prefixes":
                for record in records:
                    prefix = self.syncdata.prefixes[record]
                    prefixes.append(
                        dict(
                            prefix=prefix.prefix,
                            description=prefix.description,
                            status=prefix.status,
                            type=prefix.type,
                        )
                    )
            elif dataset == "addresses":
                for record in records:
                    address = self.syncdata.addresses[record]
                    addresses.append(
                        dict(
                            address=address.address,
                            description=address.name,
                            status=address.status,
                            dns_name=address.dns_name,
                            namespace=self.syncdata.local_ids["Global namespace"],
                        )
                    )
        logger.info(f"Nautobot: Batch-creating {len(prefixes)} prefixes")
        self.api.ipam.prefixes.create(prefixes)
        logger.info(f"Nautobot: Batch-creating {len(addresses)} addresses")
        self.api.ipam.ip_addresses.create(addresses)

    def update(self):
        for dataset, records in self._get_all_change_paths("update").items():
            with cf.ThreadPoolExecutor(
                thread_name_prefix="nautobot_update"
            ) as executor:
                for record in records:
                    executor.submit(self.update_one, dataset, record)

    def update_one(self, dataset, record):
        api_endpoint = self._get_api_endpoint(dataset)
        dataset_singular = dict(prefixes="Prefix", addresses="IP Address")[dataset]
        id_ = self.syncdata.local_ids[record]
        if dataset == "prefix":
            prefix = self.syncdata.prefixes[record]
            data = dict(
                prefix=prefix.prefix,
                description=prefix.description,
                status=prefix.status,
                type=prefix.type,
            )
        elif dataset == "addresses":
            address = self.syncdata.addresses[record]
            data = dict(
                address=address.address,
                description=address.name,
                status=address.status,
                dns_name=address.dns_name,
            )
        logger.info(f"Nautobot: Updating {dataset_singular} {record}")
        api_endpoint.update(id_, data)  # type: ignore

    def delete(self):
        for dataset, records in self._get_all_change_paths("delete").items():
            with cf.ThreadPoolExecutor(
                thread_name_prefix="nautobot_delete"
            ) as executor:
                for record in records:
                    executor.submit(self.delete_one, dataset, record)

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

        # remove this record from syncdata, so it doesn't
        # accidentally get synchronized back into the data source from which it was deleted
        getattr(self.syncdata, dataset).pop(record)

    @property
    def api(self):
        # get a thread-local copy of the api object, and returns the appropriate endpoint for the requested dataset
        if not hasattr(self._local_ns, "api"):
            self._local_ns.api = pynautobot.api(
                self.url, token=self.token.get_secret_value()
            )
        return self._local_ns.api

    def _get_api_endpoint(self, dataset) -> pynautobot.core.endpoint.Endpoint:
        endpoint_name = dict(prefixes="prefixes", addresses="ip-addresses")[dataset]
        return getattr(self.api.ipam, endpoint_name)


class BluecatManager(SyncManager):

    def __init__(self) -> None:
        super().__init__()
        self.api = BluecatSettings.from_cache().get_api_connection(multi_threaded=True)

        super().__init__()

    def load_data(self):
        raw_data = self.load_data_raw()
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

            if ip_object["properties"].get("CIDR"):
                prefix = ip_object["properties"]["CIDR"]
                local_ids[prefix] = ip_object["id"]
            elif ip_object["properties"].get("prefix"):
                prefix = ip_object["properties"]["prefix"]
                local_ids[prefix] = ip_object["id"]
            elif type_ == "address":
                address = ip_object["properties"]["address"]
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
                re.VERBOSE,
            )

            match = pattern.search(_name.lower())
            if match and match.group(1):
                status = "Reserved"
            elif match and match.group(2):
                status = "Deprecated"
            else:
                status = "Active"

            if type_ == "address":
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

                addr = str(IPAddress(address))
                addresses[addr] = IPAddressModel(
                    address=addr, name=_name, status=status, dns_name=dns_name
                )

            else:
                pfx = str(IPNetwork(prefix))
                prefixes[pfx] = PrefixModel(
                    prefix=pfx,
                    description=_name,
                    type=type_,
                    status=status,
                )

        self.syncdata = SyncData(
            prefixes=prefixes,
            addresses=addresses,
            local_ids=local_ids,
        )

    def load_data_raw(self):
        bc = self.api
        configuration_id = bc.get_configuration()["id"]
        dns_view_id = bc.get_view()["id"]
        ip_objects, dns_objects = bc.multithread_jobs(
            bc.get_ip_objects, bc.get_dns_objects
        )
        return BluecatDataRaw(
            configuration_id=configuration_id,
            dns_view_id=dns_view_id,
            ip_objects=ip_objects,
            dns_objects=dns_objects,
        )


def _validate_templates_dir(templates_dir):
    if templates_dir is None:
        templates_dir = Path(".")
    if not templates_dir.joinpath("filters.py").exists():
        logger.error(
            f"Expected to find a `filters.py` file in template repo directory '{templates_dir.resolve()}'"
        )
        logger.warning("Are you sure you're in the right directory?")
        raise typer.Exit(1)
    return templates_dir


TemplatesPath: typing.TypeAlias = typing.Annotated[
    Path, typer.Option(exists=True, callback=_validate_templates_dir)
]


@app.command()
def sync_from_bluecat(dev: bool = False):
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(thread_name_prefix="test") as executor:
        from uoft_core import Timeit

        t = Timeit()

        # decrypt secrets and initialize managers
        nb = executor.submit(lambda: NautobotManager(dev))
        bc = executor.submit(lambda: BluecatManager())
        nb = nb.result()
        bc = bc.result()

        # load data
        futures = [executor.submit(nb.load_data), executor.submit(bc.load_data)]
        [f.result() for f in cf.as_completed(futures)]

        # sync data
        nb.synchronize(bc.syncdata)

        # save data
        nb.save_data()

    runtime = t.stop().str
    print(runtime)


