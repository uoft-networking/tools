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
from pathlib import Path
import typing as t
import time
import re
from difflib import Differ
from uuid import UUID

from . import (
    Settings,
    OnOrphanAction,
    ComplianceReportGoal,
    get_intended_config,
    get_settings,
    get_api,
)
from uoft.core.types import BaseModel
from uoft.core import logging
from uoft.core.console import console

import pynautobot
from pynautobot.core.response import Record
from pynautobot.models.extras import Jobs, JobResults
from pynautobot.models.dcim import Devices as NautobotDeviceRecord
import deepdiff
import deepdiff.model
import jinja2
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm


logger = logging.getLogger(__name__)


ip_address: t.TypeAlias = str
"ip address in CIDR notation, e.g. '192.168.0.20/24'"
network_prefix: t.TypeAlias = str
"network prefix in CIDR notation, e.g. '10.0.0.0/8'"
common_id: t.TypeAlias = ip_address | network_prefix
"common id used to identify objects in both systems"

Status: t.TypeAlias = t.Literal["Active", "Reserved", "Deprecated"]
PrefixType: t.TypeAlias = t.Literal["container", "network", "pool"]


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


class DeviceModel(BaseModel):
    hostname: str
    ip_address: ip_address


Prefixes: t.TypeAlias = dict[network_prefix, PrefixModel]
Addresses: t.TypeAlias = dict[ip_address, IPAddressModel]
Devices: t.TypeAlias = dict[str, DeviceModel]


class SyncData(BaseModel):
    prefixes: Prefixes | None
    addresses: Addresses | None
    devices: Devices | None

    # the keys will be ip addresses / network cidrs / dns names, and
    # the values will be bluecat object ids or nautobot uuids
    local_ids: dict[common_id, int | str]

    @property
    def datasets(self):
        "compute the set of datasets that are present in this SyncData object"
        res = set(k for k, v in self.dict().items() if v)
        res.remove("local_ids")
        return res


class BluecatDataRaw(BaseModel):
    configuration_id: int
    dns_view_id: int
    ip_objects: list[dict]
    dns_objects: list[dict]


class NautobotDataRaw(BaseModel):
    prefixes: list[dict]
    addresses: list[dict]
    devices: list[dict]
    statuses: dict[str, Status]  # maps status id to status name
    global_namespace_id: str
    soft_delete_tag_id: str


class SyncManager:
    syncdata: SyncData
    diff: deepdiff.DeepDiff

    def __init__(self) -> None:
        self.syncdata = None  # pyright: ignore[reportAttributeAccessIssue]
        self.diff = None  # pyright: ignore[reportAttributeAccessIssue]

    def synchronize(self, source_data: SyncData):
        assert self.syncdata.datasets == source_data.datasets
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
        assert set(diff.keys()) <= expected_diff_types, (
            f"Deepdiff has identified unexpected type[s] of change: {set(diff.keys()) - expected_diff_types}"
        )

        delta = deepdiff.Delta(diff)

        new_syncdata = t.cast(SyncData, self.syncdata + delta)

        self.syncdata = new_syncdata
        self.diff = diff


def _get_all_change_paths(diff, change_type):
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
    for record in diff.tree[change_type_name]:
        record: deepdiff.model.DiffLevel
        path = t.cast(list[str], record.path(output_format="list"))

        # path lists for records added / removed look like
        # ["prefixes", "10.0.0.0/8"] or ["addresses", "192.168.0.20"],
        # path lists for records updated look like
        # ["prefixes", "10.0.0.0/8", "name"] or ["addresses", "192.168.0.20", "dns_name"]
        dataset_name = path[0]
        record_name = path[1]
        res[dataset_name].add(record_name)
    return res


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


def sync_from_bluecat(
    dev: bool = False,
    interactive: bool = True,
    on_orphan: OnOrphanAction = OnOrphanAction.prompt,
):
    from uoft.core import Timeit
    from .. import _sync
    import typer

    print = console().print

    t = Timeit()

    def done():
        runtime = t.stop().str
        print(f"Sync completed in {runtime}")

    datasets = {"prefixes", "addresses"}
    bc = _sync.BluecatTarget()
    nb = _sync.NautobotTarget(dev=dev)
    sm = _sync.SyncManager(
        source=bc,
        dest=nb,
        datasets=datasets,  # pyright: ignore[reportArgumentType]
        on_orphan=on_orphan.value,
    )

    sm.load()
    sm.synchronize()
    if sm.changes.is_empty():
        done()
        return
    if interactive:
        print({k: len(v) for k, v in sm.source.syncdata.dict().items() if v})
        print("Do you want to see a detailed breakdown of the changes?")
        if typer.confirm("Show diff?"):
            print(sm.changes)
        print("Do you want to commit these changes to Nautobot?")
        if typer.confirm("Commit changes?"):
            sm.commit()
    else:
        sm.commit()
    done()


def get_jinja_env(templates_dir: Path):
    from uoft.core import jinja

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    jinja.import_from_module(templates_dir, force=False)
    jinja._update_env(env)
    return env


def show_golden_config_data(
    device_name: str,
    dev: bool = False,
):
    nb = get_api(dev)
    device = t.cast(Record, nb.dcim.devices.get(name=device_name))
    gql_query = t.cast(str, t.cast(Record, nb.extras.graphql_queries.get(name="golden_config")).query)
    data = nb.graphql.query(gql_query, {"device_id": device.id})
    print(json.dumps(data.json["data"]["device"], indent=2))


@t.no_type_check
def trigger_golden_config_intended(
    device_name: str,
    dev: bool = False,
):
    nb = get_api(dev)
    device: Record = nb.dcim.devices.get(name=device_name)
    job = nb.extras.jobs.get(name="Generate Intended Configurations")
    job_result = nb.extras.jobs.run(job_id=job.id, data={"device": [device.id]}).job_result
    print(
        "A new `Generate Intended Configurations` job run has been triggered. Job status / results can be found here:"
    )
    print(job_result.url.replace("/api/", "/"))


def template_filter_info(
    templates_dir=Path("."),
):
    # scan the templates for uses of jinja filters
    found_filters = set()
    import re

    for template_file in templates_dir.glob("templates/**/*.j2"):
        logger.info(f"Scanning {template_file}")
        for match in re.finditer(r"\|\s*([a-zA-Z_][a-zA-Z0-9_]*)", template_file.read_text()):
            filter_name = match.group(1).strip()
            found_filters.add(filter_name)
            logger.debug(filter_name)
    found_filters = sorted(found_filters)
    found_filters = "\n- ".join(found_filters)
    logger.info(f"Your templates use the following filters: \n- {found_filters}")
    env = get_jinja_env(templates_dir)
    filters = [f for f in env.filters]
    filters = sorted(filters)
    filters = "\n- ".join(filters)
    logger.info(f"You have the following filters available: \n- {filters}")

_cached_jinja_env = None

def test_golden_config_templates(
    device_name: str,
    override_status: str | None = None,
    templates_dir: Path = Path("."),
    dev: bool = False,
    print_output: bool = True,
    cache_jinja_env: bool = True,
):
    import typer
    global _cached_jinja_env

    nb = get_api(dev)
    device = t.cast(Record | None, nb.dcim.devices.get(name=device_name))
    if not device:
        logger.error(f"Device {device_name} not found in Nautobot")
        raise typer.Exit(1)
    gql_query = templates_dir.joinpath("graphql/golden_config.graphql").read_text()
    data = nb.graphql.query(gql_query, {"device_id": device.id}).json["data"]["device"]

    if override_status:
        assert override_status in [
            "Active",
            "Planned",
        ], "Status must be either 'Active' or 'Planned'"
        data["status"]["name"] = override_status

    # we need to copy the behaviour of the transposer function without actually importing it
    data["data"] = data.copy()

    # we need to set up a jinja environment which mimics the behaviour of the one set up by
    # nautobot for rendering golden config templates
    if cache_jinja_env and _cached_jinja_env:
        env = _cached_jinja_env
    else:
        env = get_jinja_env(templates_dir)
        if cache_jinja_env:
            _cached_jinja_env = env

    tmpl = env.get_template("templates/entrypoint.j2")
    text = tmpl.render(data)
    if print_output:
        print(text)
    return text


def run_job(dev: bool, job_name: str, data: dict):
    nb = get_api(dev)
    con = console()
    job = t.cast(Jobs | None, nb.extras.jobs.get(name=job_name))
    assert job, f"Job '{job_name}' not found in Nautobot"
    job_result: JobResults = nb.extras.jobs.run(  # pyright: ignore
        job_id=job.id, data=data
    ).job_result  # pyright: ignore
    con.print(f"A new '{job_name}' job run has been triggered. Job status / results can be found here:")
    url = t.cast(str, job_result.url).replace("/api/", "/")
    con.print(f"[link={url}]{url}[/link]")
    con.print("Waiting for job to complete...")
    while True:
        new_result = t.cast(JobResults, nb.extras.job_results.get(job_result.id))
        status = t.cast(str, t.cast(Record, new_result.status).value)
        if status not in ["STARTED", "PENDING"]:
            con.print(" ")
            break
        con.print(".", end="")
        time.sleep(1)
    logger.success("Job completed with status: " + status)
    if status != "SUCCESS":
        logger.error("Job failed")
        logger.error(new_result)
    return new_result


@t.no_type_check
def update_golden_config_repo(dev=False):
    nb = get_api(dev)
    gitrepo = nb.extras.git_repositories.get(name="golden_config_templates")
    job_result = run_job(dev, "Git Repository: Sync", {"repository": gitrepo.id})
    return job_result


def push_changes_to_nautobot(
    templates_dir: Path = Path("."),
    dev: bool = False,
):
    import subprocess

    # make sure git status is clean
    git_status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, cwd=templates_dir)
    assert git_status.returncode == 0, "This command is meant to be run AFTER you've committed your changes."

    logger.info("Pushing local changes to gitlab")
    subprocess.run(["git", "push"], check=True, cwd=templates_dir)

    logger.info("Telling nautobot to pull the changes")
    return update_golden_config_repo(dev=dev)


def test_templates_in_nautobot(
    templates_dir: Path = Path("."),
    dev: bool = False,
):
    push_changes_to_nautobot(templates_dir, dev)
    nb = get_api(dev)
    all_platform_uuids: list[str] = [
        p.id  # pyright: ignore
        for p in nb.dcim.platforms.all()
    ]  # pyright: ignore
    job_result = run_job(dev, "Generate Intended Configurations", {"platform": all_platform_uuids})
    run_job(
        dev,
        "Perform Configuration Compliance",
        data={"status": [t.cast(Record, nb.extras.statuses.get(name="Active")).id]},
    )
    return job_result


def _device_family_id(nb, prompt, model):
    device_families_by_name = {}
    for family in nb.dcim.device_families.all():
        device_families_by_name[family.name] = family.id

    matching_families = [f for f in device_families_by_name if f in model]
    if len(matching_families) == 1:
        logger.info(f"Device family found for {model}: {matching_families[0]}")
        return device_families_by_name[matching_families[0]]
    elif len(matching_families) > 1:
        family_name = prompt.get_from_choices(
            "device_family",
            matching_families,
            "Select a device family for this device type",
        )
        return device_families_by_name[family_name]
    else:
        logger.info(f"Unable to automatically determine device family based on part number {model}")
        if not prompt.get_bool(
            "has_device_family",
            "Should this device_type belong to a device family?",
        ):
            return None
        family_name = prompt.get_from_choices(
            "family_name",
            ["Create a new one...", *list(device_families_by_name.keys())],
            "Select a device family for this device type",
        )
        if family_name == "Create a new one...":
            family_name = Settings._prompt().get_string(
                "device_family",
                'Enter a device family name for this device type (Ex: "C9300")',
            )
            family = nb.dcim.device_families.create(name=family_name)
            return family.id
        else:
            return device_families_by_name[family_name]


def _manufacturer_id(nb, manufacturer):
    mfg = nb.dcim.manufacturers.get(name=manufacturer)
    if mfg:
        logger.info(f"Manufacturer {manufacturer} found with id {mfg.id}")
    else:
        logger.info(f"Manufacturer {manufacturer} not found, creating...")
        mfg = nb.dcim.manufacturers.create(name=manufacturer)
    return mfg.id


def device_type_add_or_update(
    dev: bool = False,
):
    """
    create or update a device type in nautobot based on a device type file in the device-types repo
    """

    prompt = Settings._prompt()

    manufacturers = [str(p.stem) for p in Path("device-types").iterdir() if p.is_dir()]
    manufacturer = prompt.get_from_choices(
        "manufacturer: ",
        choices=manufacturers,
        description="Select a manufacturer for this device type",
    )

    model = prompt.get_from_choices(
        "model: ",
        [f.stem for f in Path("device-types").joinpath(manufacturer).glob("*.yaml")],
        description="Select a model for this device type",
        fuzzy_search=True,
    )
    # make sure the specified manufacturer and model exist in the device-types library
    device_type_file = Path("device-types").joinpath(manufacturer, f"{model}.yaml")

    # read the device type file
    from uoft.core.yaml import loads

    device_type = loads(device_type_file.read_text())

    prompt = Settings._prompt()

    nb = get_api(dev)

    # the device_type dictionary ALMOST perfectly matches the structure expected by the Nautobot API
    # for device_types
    _manufacturer_id(nb, manufacturer)
    model = device_type["model"]

    if existing_device_type := t.cast(
        Record,
        nb.dcim.device_types.get(model=model, manufacturer=manufacturer),
    ):
        logger.info(f"Device type {model} already exists in Nautobot")
        if not prompt.get_bool(
            "update_device_type",
            "Would you like to update this device type?",
        ):
            return
        device_type_id = existing_device_type.id
    else:
        nb_data = dict(
            front_image=device_type.get("front_image"),
            rear_image=device_type.get("rear_image"),
            model=device_type.get("model"),
            part_number=device_type.get("part_number"),
            u_height=device_type.get("u_height"),
            is_full_depth=device_type.get("is_full_depth"),
            subdevice_role=device_type.get("subdevice_role"),
            comments=device_type.get("comments"),
            family=_device_family_id(nb, prompt, device_type.get("part_number")),
            manufacturer=_manufacturer_id(nb, manufacturer),
        )
        if nb_data["comments"] is None:
            del nb_data["comments"]

        try:
            del nb_data["front_image"]
            del nb_data["rear_image"]
        except KeyError:
            pass

        logger.info(f"Creating device type {model}...")
        res = t.cast(Record, nb.dcim.device_types.create(nb_data))
        device_type_id = res.id

    logger.info(f"Device type {model} created with id {device_type_id}")

    def _populate_interface(
        interface, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        interface_data = dict(
            name=interface.get("name"),
            type=interface.get("type"),
            mgmt_only=interface.get("mgmt_only"),
            description=interface.get("description"),
        )
        if parent_type == "device":
            interface_data["device_type"] = parent_id
        else:
            interface_data["module_type"] = parent_id
        if interface_data["description"] is None:
            del interface_data["description"]
        if interface_data["mgmt_only"] is None:
            del interface_data["mgmt_only"]
        try:
            nb.dcim.interface_templates.create(interface_data)
            logger.info(f"Created interface {interface_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all interfaces will already exist
            # in this case, we can ignore the error
            pass

    def _populate_console_port(
        console_port, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        console_port_data = dict(
            name=console_port.get("name"),
            type=console_port.get("type"),
            description=console_port.get("description"),
        )
        if parent_type == "device":
            console_port_data["device_type"] = parent_id
        else:
            console_port_data["module_type"] = parent_id
        if console_port_data["description"] is None:
            del console_port_data["description"]
        try:
            nb.dcim.console_port_templates.create(console_port_data)
            logger.info(f"Created console port {console_port_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all console ports
            # will already exist. in this case, we can ignore the error
            pass

    def _populate_power_port(
        power_port, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        power_port_data = dict(
            name=power_port.get("name"),
            type=power_port.get("type"),
            description=power_port.get("description"),
        )
        if parent_type == "device":
            power_port_data["device_type"] = parent_id
        else:
            power_port_data["module_type"] = parent_id
        if power_port_data["description"] is None:
            del power_port_data["description"]
        try:
            nb.dcim.power_port_templates.create(power_port_data)
            logger.info(f"Created power port {power_port_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all power ports
            # will already exist. in this case, we can ignore the error
            pass

    _rear_ports_defined = {}

    def _populate_rear_port(
        rear_port, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        rear_port_data = dict(
            name=rear_port.get("name"),
            type=rear_port.get("type"),
            positions=rear_port.get("positions"),
            description=rear_port.get("description"),
        )
        if parent_type == "device":
            rear_port_data["device_type"] = parent_id
        else:
            rear_port_data["module_type"] = parent_id
        if rear_port_data["description"] is None:
            del rear_port_data["description"]
        try:
            record = nb.dcim.rear_port_templates.create(rear_port_data)
            _rear_ports_defined[rear_port_data["name"]] = record.id  # pyright: ignore
            logger.info(f"Created rear port {rear_port_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all rear ports
            # will already exist. in this case, we can ignore the error
            record = nb.dcim.rear_port_templates.get(name=rear_port_data["name"])
            _rear_ports_defined[rear_port_data["name"]] = record.id  # pyright: ignore
            logger.info(f"Found existing rear port {rear_port_data['name']}")

    def _populate_front_port(
        front_port, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        front_port_data = dict(
            name=front_port.get("name"),
            type=front_port.get("type"),
            rear_port_position=front_port.get("rear_port_position"),
            description=front_port.get("description"),
        )
        rear_port_name = front_port["rear_port"]
        rear_port_template = _rear_ports_defined.get(rear_port_name)
        if parent_type == "device":
            front_port_data["device_type"] = parent_id
            if not rear_port_template:
                rear_port_template = nb.dcim.rear_port_templates.get(
                    device_type=device_type_id,
                    name=rear_port_name,
                ).id  # pyright: ignore
        else:
            front_port_data["module_type"] = parent_id
            if not rear_port_template:
                rear_port_template = nb.dcim.rear_port_templates.get(
                    module_type=parent_id,
                    name=rear_port_name,
                ).id  # pyright: ignore
        if not rear_port_template:
            logger.error(f"Rear port {rear_port_name} not found for front port {front_port['name']}")
            return
        front_port_data["rear_port_template"] = rear_port_template
        if front_port_data["description"] is None:
            del front_port_data["description"]
        try:
            nb.dcim.front_port_templates.create(front_port_data)
            logger.info(f"Created front port {front_port_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all front ports
            # will already exist. in this case, we can ignore the error
            pass

    def _create_module_type(manufacturer):
        modules_available = [f.stem for f in Path("module-types").joinpath(manufacturer).glob("*.yaml")]
        module_file_name = prompt.get_from_choices(
            "module",
            modules_available,
            "Select a module type to link to this module bay",
        )
        module_file = Path("module-types").joinpath(manufacturer, f"{module_file_name}.yaml")
        module_data = loads(module_file.read_text())
        module_type_data = dict(
            name=module_data.get("name"),
            model=module_data.get("model"),
            part_number=module_data.get("part_number"),
            manufacturer=_manufacturer_id(nb, manufacturer),
        )
        try:
            module_type_record = nb.dcim.module_types.create(module_type_data)
            _populate_device_type_components(module_data, parent_type="module", parent_id=module_type_record.id)  # pyright: ignore[reportAttributeAccessIssue]
            logger.info(f"Created module type {module_type_data['name']}")
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all module types
            # will already exist. in this case, we can ignore the error
            pass

    def _populate_module_bay(
        module_bay, parent_type: t.Literal["device", "module"] = "module", parent_id: str | None = None
    ):
        mb_name = module_bay.get("name")
        logger.info(f"{model} defines a module bay called {mb_name}.")
        while prompt.get_bool(
            "Would you like to import a[nother] module type from this manufacturer?",
            "Would you like to import a[nother] module type from this manufacturer?",
        ):
            _create_module_type(manufacturer)
        module_bay_data = dict(
            name=mb_name,
            description=module_bay.get("description"),
            position=module_bay.get("position"),
        )
        if parent_type == "device":
            module_bay_data["device_type"] = parent_id
        else:
            module_bay_data["module_type"] = parent_id
        try:
            nb.dcim.module_bay_templates.create(module_bay_data)
            logger.info(f"Created module bay {module_bay_data['name']}")
        except pynautobot.RequestError:
            pass

    def _populate_device_type_components(
        component_data, parent_type: t.Literal["device", "module"] = "device", parent_id: str | None = None
    ):
        # component_data could be the device_type dict,
        # or it could be a dict loaded from a module
        if interfaces := component_data.get("interfaces"):
            logger.info(f"Creating interfaces for {model}")
            for interface in interfaces:
                _populate_interface(interface, parent_type=parent_type, parent_id=parent_id)

        if console_ports := component_data.get("console-ports"):
            logger.info(f"Creating console ports for {model}")
            for console_port in console_ports:
                _populate_console_port(console_port, parent_type=parent_type, parent_id=parent_id)

        if power_ports := component_data.get("power-ports"):
            logger.info(f"Creating power ports for {model}")
            for power_port in power_ports:
                _populate_power_port(power_port, parent_type=parent_type, parent_id=parent_id)

        if rear_ports := component_data.get("rear-ports"):
            logger.info(f"Creating rear ports for {model}")
            for rear_port in rear_ports:
                _populate_rear_port(rear_port, parent_type=parent_type, parent_id=parent_id)
        if front_ports := component_data.get("front-ports"):
            logger.info(f"Creating front ports for {model}")
            for front_port in front_ports:
                _populate_front_port(front_port, parent_type=parent_type, parent_id=parent_id)

        if module_bays := component_data.get("module-bays"):
            for module_bay in module_bays:
                _populate_module_bay(module_bay, parent_type=parent_type, parent_id=parent_id)

    _populate_device_type_components(device_type, parent_type="device", parent_id=device_type_id)

    logger.info("Done!")


def _select_from_queryset(
    prompt,
    nb,
    queryset,
    name,
    msg,
    key="name",
    create_new_callback: t.Callable[[], tuple[str, str]] | None = None,
    **kwargs,
) -> tuple[str, str]:
    mapping: dict[str, str] = {obj[key]: obj["id"] for obj in queryset}
    choices = list(mapping.keys())
    if create_new_callback:
        choices = ["Create a new one...", *choices]
    choice: str = prompt.get_from_choices(
        name,
        list(mapping.keys()),
        msg,
        completer_opts=dict(ignore_case=True),
        **kwargs,
    )
    if create_new_callback and choice == "Create a new one...":
        return create_new_callback()
    return choice, mapping[choice]


def new_switch(
    dev: bool = False,
):
    """
    Create a new switch in Nautobot.

    This function will create a new switch in Nautobot with the necessary configurations.
    It will prompt for the device type and other required information.
    """
    prompt = Settings._prompt()
    nb = get_api(dev)

    name = prompt.get_string("name", "Enter the name of the switch")

    logger.info("Loading list of available Manufacturers from Nautobot...")
    manufacturer, manufacturer_id = _select_from_queryset(
        prompt,
        nb,
        nb.dcim.manufacturers.all(),
        "manufacturer",
        "Select a manufacturer for this switch",
    )

    logger.info(f"Loading list of available {manufacturer} Device Types from Nautobot...")
    dt, dt_id = _select_from_queryset(
        prompt,
        nb,
        nb.dcim.device_types.filter(manufacturer=manufacturer_id),
        "device_type",
        "Select a device type for this switch",
        key="model",
        fuzzy_search=True,
    )

    logger.info("Checking to see if this device type has been deployed before...")
    if nb.dcim.devices.count(device_type=dt_id) == 0:
        if not prompt.get_bool(
            var="confirm_device_type",
            description=f"There are currently 0 switches in Nautobot with device type '{dt}'. "
            "Are you sure you picked the right device type?",
        ):
            return

    platform, platform_id = _select_from_queryset(
        prompt,
        nb,
        nb.dcim.platforms.filter(manufacturer=manufacturer_id),
        "platform",
        "Select a platform for this switch",
        fuzzy_search=True,
    )

    logger.info("Loading list of Device Roles from Nautobot...")
    role, role_id = _select_from_queryset(
        prompt,
        nb,
        nb.extras.roles.filter(content_types="dcim.device"),
        "role",
        "What kind of switch are you creating?",
    )

    logger.info("Loading list of Locations from Nautobot...")
    locations = {
        t.cast(str, obj["display"]): t.cast(str, obj["id"]) for obj in t.cast(list[Record], nb.dcim.locations.all())
    }

    def _new_room():
        building_name = prompt.get_from_choices(
            "Building",
            list(locations.keys()),
            "The building which this room is in",
            completer_opts=dict(ignore_case=True),
            fuzzy_search=True,
            generate_rprompt=False,
        )
        location_name = prompt.get_string("room_name", "Enter the name of the location")
        logger.info(f"Creating new location '{location_name}'...")
        location_record = t.cast(
            Record,
            nb.dcim.locations.create(
                name=location_name,
                location_type={"name": "Room"},
                parent=locations[building_name],
                status={"name": "Active"},
                custom_fields=dict(room_number=prompt.get_string("room_number", "Enter the room number (ex. AC290)")),
            ),
        )
        return location_name, t.cast(str, location_record.id)

    choice = prompt.get_from_choices(
        "location",
        ["Create a new one...", *list(locations.keys())],
        "Select a location for this switch",
        completer_opts=dict(ignore_case=True),
        fuzzy_search=True,
        generate_rprompt=False,
    )
    if choice == "Create a new one...":
        location, location_id = _new_room()
    else:
        location, location_id = choice, locations[choice]
    logger.info(f"Selected location {location} with id {location_id}")

    vlan_groups = t.cast(list[Record], nb.ipam.vlan_groups.all())
    vlan_group_name = prompt.get_from_choices(
        "vlan_group",
        [t.cast(str, vg.name) for vg in vlan_groups],
        "Select a VLAN Group for this switch",
    )
    vlan_group = next(vg for vg in vlan_groups if vg.name == vlan_group_name)
    logger.info(f"Assigning VLAN Group {vlan_group_name} to {name}...")

    # Tags
    tags = []
    logger.info("Loading list of available device Tags from Nautobot...")
    available_tags = {
        t.cast(str, tag["name"]): t.cast(str, tag["id"])
        for tag in t.cast(list[Record], nb.extras.tags.filter(content_types="dcim.device"))
    }
    while True:
        if not prompt.get_bool("add_tag", "Would you like to add a tag to this switch?"):
            break
        tag_name = prompt.get_from_choices(
            "tag",
            list(available_tags.keys()),
            "Select a tag to add to this switch",
        )
        tags.append(available_tags[tag_name])

    if role == "Distribution Switches":
        # figure out vlan group association
        logger.warning(
            "VLAN group association not yet supported. "
            "you will need to manually create a vlan group for this dist switch and associate it with the switch"
        )

    # Set up the primary interface
    # on Dist and Core switches, this'll be Loopback0

    # On all other switches, this'll be Vlan900
    if role in ["Distribution Switches", "Core Switches"]:
        interface_name = "Loopback0"
    else:
        interface_name = "Vlan900"

    primary_ip4 = prompt.get_cidr(
        "primary_ip4",
        "Primary IPv4 address for this switch in CIDR (ex aa.bb.cc.dd/ee)",
    )

    # optionally override config_context.os_version
    config_context = {}
    if prompt.get_bool(
        "override_os_version",
        "Would you like to override the OS version for this device?",
    ):
        os_version = prompt.get_string("os_version", "Enter the OS version for this device")
        config_context["os_version"] = os_version

    logger.info("Checking to see if Device already exists in Nautobot...")
    if device := t.cast(NautobotDeviceRecord | None, nb.dcim.devices.get(name=name)):
        logger.info(f"Device {name} already exists in Nautobot, updating...")
        nb.dcim.devices.update(
            id=device.id,  # pyright: ignore
            data=dict(
                device_type=dt_id,
                platform=platform_id,
                role=role_id,
                status="Planned",
                location=location_id,
                vlan_group=vlan_group.id,
                manufacturer=manufacturer_id,
                tags=tags,
                local_config_context_data=config_context,
            ),
        )
    else:
        logger.info(f"Creating new device {name} in Nautobot...")
        device = t.cast(
            NautobotDeviceRecord,
            nb.dcim.devices.create(
                name=name,
                device_type=dt_id,
                platform=platform_id,
                role=role_id,
                status="Planned",
                location=location_id,
                vlan_group=vlan_group.id,
                manufacturer=manufacturer_id,
                tags=tags,
            ),
        )

    logger.info(f"Checking to see if {name}/{interface_name} already exists in Nautobot...")
    mgmt_interface = nb.dcim.interfaces.get(device=device.id, name=interface_name)
    if not mgmt_interface:
        logger.info(f"Creating primary interface {interface_name} for {name} in Nautobot...")
        mgmt_interface = nb.dcim.interfaces.create(
            device=device.id,
            name=interface_name,
            type="virtual",
            status="Active",
        )
    mgmt_interface = t.cast(Record, mgmt_interface)

    logger.info(f"Checking to see if {primary_ip4} already exists in Nautobot...")
    host, _, prefix_length = primary_ip4.partition("/")
    if ipv4 := t.cast(Record, nb.ipam.ip_addresses.get(q=host)):
        logger.info(f"IP Address {primary_ip4} already exists in Nautobot, updating...")
        if ipv4.mask_length != int(prefix_length):
            logger.error(
                f"IP Address {primary_ip4} already exists in Nautobot as {ipv4.address}, "
                "Please rerun script with this CIDR or update the IP address prefix manually in Nautobot."
            )
            return
        nb.ipam.ip_addresses.update(
            id=ipv4.id,  # pyright: ignore
            data=dict(
                status="Active",
                description=name,
                dns_name=f"{name}.netmgmt.utsc.utoronto.ca",
            ),
        )
    else:
        logger.info(f"Creating new IP Address {primary_ip4} in Nautobot...")
        ipv4 = t.cast(
            Record,
            nb.ipam.ip_addresses.create(
                address=primary_ip4,
                status="Active",
                namespace={"name": "Global"},
                description=name,
                dns_name=f"{name}.netmgmt.utsc.utoronto.ca",
            ),
        )
        if prompt.get_bool("push to bluecat", "Would you like to push this IP address to Bluecat?"):
            # from uoft.bluecat.cli import add_or_update_ip

            raise NotImplementedError("Bluecat integration not yet implemented, talk to Alex T")

    logger.info(f"Associating {primary_ip4} with {interface_name}...")
    try:
        nb.ipam.ip_address_to_interface.create(
            ip_address=ipv4.id,
            interface=mgmt_interface.id,
        )
    except pynautobot.RequestError as e:
        if "must make a unique set" in e.args[0]:
            logger.info(f"IP Address {primary_ip4} is already associated with {interface_name}")
        else:
            raise e

    logger.info(f"Assigning {primary_ip4} as Primary IP for {name}...")
    device.primary_ip4 = ipv4  # pyright: ignore[reportAttributeAccessIssue]

    device.save()

    logger.info("Done!")


def regen_interfaces(
    device_name: str,
    dev: bool = False,
):
    """
    Regenerate nautobot switch interfaces from a device type template

    This script would be useful if, for example, you're replacing a switch with a newer model,,
    while keeping the hostname and ip address the same, and you've already gone into
    the switch's entry in nautobot,
    updated the switch's manufacturer, platform, and device type fields,
    and have already deleted the old interfaces related to the switch's previous device type.

    When run, this script will generate new interface / console port / power port entries for this switch in nautobot
    based on the interface / console port / power port entries in the device type assigned to this switch
    """
    nb = get_api(dev)
    device = t.cast(Record, nb.dcim.devices.get(name=device_name))
    device_type: Record = nb.dcim.device_types.get(
        id=device.device_type.id  # pyright: ignore
    )  # pyright: ignore
    logger.info(f"Regenerating entries for {device_name} based on device type {device_type.model}")
    logger.info("Regenerating interfaces...")
    for i_t in t.cast(list[Record], nb.dcim.interface_templates.filter(device_type=device_type.id)):
        try:
            nb.dcim.interfaces.create(
                device=device.id,
                name=i_t.name,
                label=i_t.label,
                type=i_t.type.value,  # pyright: ignore[reportOptionalMemberAccess]
                mgmt_only=i_t.mgmt_only,
                description=i_t.description,
                status="Active",
            )
        except pynautobot.RequestError as e:
            if "must make a unique set" in e.args[0]:
                logger.info(f"Interface {i_t.name} already exists")
            else:
                raise e
    logger.info("Regenerating console ports...")
    for c_t in t.cast(list[Record], nb.dcim.console_port_templates.filter(device_type=device_type.id)):
        nb.dcim.console_ports.create(
            device=device.id,
            name=c_t.name,
            label=c_t.label,
            type=c_t.type.value,  # pyright: ignore[reportOptionalMemberAccess]
            description=c_t.description,
        )
    logger.info("Regenerating power ports...")
    for p_t in t.cast(list[Record], nb.dcim.power_port_templates.filter(device_type=device_type.id)):
        nb.dcim.power_ports.create(
            device=device.id,
            name=p_t.name,
            label=p_t.label,
            type=p_t.type.value,  # pyright: ignore[reportOptionalMemberAccess]
            description=p_t.description,
        )
    logger.success("Done")


@t.no_type_check
def rebuild_switch(
    set_status_to_planned: bool = False,
    dev: bool = False,
):
    """
    Rebuild a switch in Nautobot against a new device type

    This script would be useful if, for example, you're replacing a switch with a newer model,
    while keeping the hostname and ip address the same.
    """
    prompt = Settings._prompt()
    nb = get_api(dev)

    name = prompt.get_string("name", "Enter the name of the switch")

    device = nb.dcim.devices.get(name=name)
    if not device:
        logger.error(f"Device {name} not found in Nautobot")
        return

    old_device_type = device.device_type.model

    logger.info("Loading list of available Manufacturers from Nautobot...")
    manufacturer, manufacturer_id = _select_from_queryset(
        prompt,
        nb,
        nb.dcim.manufacturers.all(),
        "manufacturer",
        "Select a manufacturer for this switch",
    )

    logger.info(f"Loading list of available {manufacturer} Device Types from Nautobot...")
    device_type, dt_id = _select_from_queryset(
        prompt,
        nb,
        nb.dcim.device_types.filter(manufacturer=manufacturer_id),
        "device_type",
        "Select a device type for this switch",
        key="model",
        fuzzy_search=True,
    )

    logger.info("Checking to see if this device type has been deployed before...")
    if nb.dcim.devices.count(device_type=dt_id) == 0:
        if not prompt.get_bool(
            var="confirm_device_type",
            description=f"There are currently 0 switches in Nautobot with device type '{device_type}'. "
            "Are you sure you want to use this device type?",
        ):
            return

    platforms = nb.dcim.platforms.filter(manufacturer=manufacturer_id)
    if len(platforms) > 1:
        platform = prompt.get_from_choices(
            "platform",
            [p.name for p in platforms],
            "Select a platform for this switch",
        )
        platform = next(p for p in platforms if p.name == platform)
    elif len(platforms) == 1:
        platform = platforms[0]
    else:
        platform = None
    # find all interfaces / console ports / power ports associated with this device which came from the old device type
    # delete them
    old_interfaces = [i.name for i in nb.dcim.interface_templates.filter(device_type=device.device_type.id)]
    logger.warning("This script will delete the following interfaces:")
    logger.info(old_interfaces)
    if not prompt.get_bool("delete_interfaces", "Do you want to continue?"):
        return
    for interface in nb.dcim.interfaces.filter(device_id=device.id):
        if interface.name in old_interfaces:
            interface.delete()

    logger.info("Deleting old console ports...")
    old_console_ports = [c.name for c in nb.dcim.console_port_templates.filter(device_type=device.device_type.id)]
    for console_port in nb.dcim.console_ports.filter(device=device.id):
        if console_port.name in old_console_ports:
            console_port.delete()

    logger.info("Deleting old power ports...")
    old_power_ports = [p.name for p in nb.dcim.power_port_templates.filter(device_type=device.device_type.id)]
    for power_port in nb.dcim.power_ports.filter(device=device.id):
        if power_port.name in old_power_ports:
            power_port.delete()

    logger.info("Updating device type...")
    device.manufacturer = manufacturer
    device.device_type = dt_id
    if platform:
        device.platform = platform

    if set_status_to_planned:
        device.status = "Planned"

    device.save()

    # create new interfaces / console ports / power ports based on the new device type
    regen_interfaces(name, dev)

    # Add a note to the device object
    device.notes.create(dict(note=f"Device has been rebuilt from device type {old_device_type} to {device_type}"))


def generate_compliance_commands(
    feature: str = "base",
    goal: ComplianceReportGoal = ComplianceReportGoal.add,
    filters: list[str] | None = None,
    sub_filters: list[str] | None = None,
    merge_with: Path | None = None,
    top_level_only: bool = False,
    prefix_when_merging: bool = False,
):
    """
    Generate compliance commands for network devices based on compliance reports.
    This function processes compliance data for a specified feature and generates the necessary configuration commands
    to either add missing configuration or remove extra configuration from devices. The commands can be filtered,
    flattened, and optionally merged with existing data in a JSON file.
    Args:
        feature (str): The compliance feature to process. Defaults to "base".
        goal (ComplianceReportGoal): The compliance goal, either to add missing config or remove extra config.
        filters (list[str] | None): List of string filters to apply to the configuration commands.
        sub_filters (list[str] | None): List of sub-filters to further refine the configuration commands.
        merge_with (Path | None): Path to a JSON file to merge the generated commands with existing data.
        top_level_only (bool): If True, only top-level configuration commands are considered.
        prefix_when_merging (bool): If True, new commands are prefixed when merging with existing data.
    Returns:
        None
    Side Effects:
        - Prints the generated commands as a JSON object if `merge_with` is not provided.
        - If `merge_with` is provided, updates the specified JSON file with the merged commands.
    Raises:
        AssertionError: If `merge_with` is provided but the file does not exist.
    """

    filters = filters or []
    sub_filters = sub_filters or []
    res = {}
    for report in get_compliance_data(feature):
        if goal == ComplianceReportGoal.add:
            config = report.missing  # missing config to add
        elif goal == ComplianceReportGoal.remove:
            config = report.extra  # extra config to removes
        if not config:
            logger.warning(f"{report.device.name} has no config to {goal}, skipping...")
            continue
        matched_commands = filter_config(
            config=config,
            filters=filters,
            sub_filters=sub_filters,
            top_level_only=top_level_only,
        )
        if matched_commands:
            if goal == ComplianceReportGoal.remove:
                matched_commands = [f"no {c.splitlines()[0]}" for c in matched_commands]
            else:
                flattened_commands = []
                for c in matched_commands:
                    flattened_commands.extend(c.splitlines())
                matched_commands = flattened_commands
            res[report.device.name] = matched_commands
    if merge_with:
        assert merge_with.exists(), f"File {merge_with} does not exist"
        existing_data = json.loads(merge_with.read_text())
        for k, v in res.items():
            if prefix_when_merging:
                existing_data[k] = v + existing_data.get(k, [])
            else:
                existing_data[k] = existing_data.get(k, []) + v
        res = existing_data
        merge_with.write_text(json.dumps(res, indent=2))
    else:
        print(json.dumps(res, indent=2))


class ComplianceReportDevice(BaseModel):
    name: str
    platform: str
    status: str
    software_version: str | None
    device_type: str


class ComplianceReport(BaseModel):
    device: ComplianceReportDevice
    feature: str
    actual: str
    intended: str
    missing: str
    extra: str
    in_compliance: bool


def get_compliance_data(feature) -> list[ComplianceReport]:
    nb = get_settings(False).api_connection()
    res = []
    d = nb.graphql.query(
        variables={"feature": feature},
        query="""
query ($feature: String) {
  config_compliances (feature: [$feature], device_status: "Active", compliance: false) {
    compliance
    rule {
      feature { name }
    }
    intended
    actual
    missing
    extra
    device {
      name
      platform { name }
      status { name }
      device_type { model }
      software_version { version }
    }
  }
}
""",
    )
    if d.json.get("errors"):
        logger.error(d.json["errors"])
        raise Exception(f"Error fetching compliance data: {d.json['errors']}")
    for r in d.json["data"]["config_compliances"]:
        report = ComplianceReport(
            device=ComplianceReportDevice(
                name=r["device"]["name"],
                platform=r["device"]["platform"]["name"],
                status=r["device"]["status"]["name"],
                software_version=(
                    r["device"]["software_version"]["version"] if r["device"]["software_version"] else None
                ),
                device_type=r["device"]["device_type"]["model"],
            ),
            feature=r["rule"]["feature"]["name"],
            actual=r["actual"],
            intended=r["intended"],
            missing=r["missing"],
            extra=r["extra"],
            in_compliance=r["compliance"],
        )
        res.append(report)
    return res


def _group_config(config: str) -> list[str]:
    # Break up the config snippet into a list of lines.
    # Group lines that start with an indent in with the non-indented line above them
    return re.split(r"\n(?!\s)", config)


def filter_config(
    config: str,
    filters: list[str],
    sub_filters: list[str] | None = None,
    top_level_only: bool = False,
):
    """
    Filters and extracts configuration chunks from a given configuration string based on specified filters.
    Args:
        config: The configuration string to be filtered.
        filters: List of regular expression patterns to match against the top-level
            lines of each configuration chunk.
        sub_filters: List of regular expression patterns to further filter sub-lines
            within matched chunks. Defaults to None.
        top_level_only: If True, only the top-level line of each matched chunk is
            included in the result. If False, the entire chunk or filtered sub-lines are included.
            Defaults to False.
    Returns:
        A list of configuration chunks or lines that match the specified filters.
    Notes:
        - The configuration is first grouped into chunks,
          where each chunk starts with a non-indented line followed by its indented sub-lines.
        - If `sub_filters` is provided, only sub-lines within matched chunks that match any of
          the `sub_filters` are included.
        - If `top_level_only` is True, only the first line of each matched chunk is returned,
          and `sub_filters` is ignored.
    """

    grouped_config = _group_config(config)
    sub_filters = sub_filters or []
    # Break up the config snippet into a list of lines.
    # Group lines that start with an indent in with the non-indented line above them
    res: list[str] = []
    for chunk in grouped_config:
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        if not any([re.search(f, lines[0]) for f in filters]):
            continue
        if not sub_filters:
            if top_level_only:
                res.append(lines[0])
            else:
                # add the whole chunk to res
                res.append("\n".join(lines))
        else:
            # filter the chunk by sub_filters
            filtered_chunk = [lines[0]]
            for line in lines[1:]:
                if any([re.search(f, line) for f in sub_filters]):
                    filtered_chunk.append(line)
            if len(filtered_chunk) > 1:
                res.append("\n".join(filtered_chunk))
    return res


def _sort_config_snippet(snippet: str):
    return "\n".join(sorted(_group_config(snippet)))


def _devices_with_matching_line(
    line: str,
    compliance_data: list[ComplianceReport],
    config_type: t.Literal["actual", "intended"] = "actual",
):
    logger.info(f"Please wait, searching for devices with matching line: '{line}'")
    matching_devices = [c.device for c in compliance_data if line in getattr(c, config_type)]
    tab = Table(title=f"Devices with matching line: {line}")
    tab.add_column("Device")
    tab.add_column("Status")
    tab.add_column("Platform Version")
    tab.add_column("Device Type")
    for device in matching_devices:
        tab.add_row(device.name, device.status, device.software_version, device.device_type)
    return tab


def _generate_report_comparison_table(report: ComplianceReport):
    tab = Table(title=report.device.name)
    tab.add_column("Actual")
    tab.add_column("Intended")
    actual = _sort_config_snippet(report.actual)
    intended = _sort_config_snippet(report.intended)
    diff = Differ().compare(actual.splitlines(), intended.splitlines())
    render_intended = []
    render_actual = []
    extra_config = []
    missing_config = []
    for line in diff:
        marker, line = line[:2], line[2:]
        if not line:
            continue
        if marker == "  ":
            render_actual.append(line + "\n")
            render_intended.append(line + "\n")
        if marker == "+ ":
            render_intended.append(f"[green]{line}[/green]\n")
            missing_config.append(line)
        if marker == "- ":
            render_actual.append(f"[red]{line}[/red]\n")
            extra_config.append(line)
    tab.add_row("".join(render_actual), "".join(render_intended))
    return tab, extra_config, missing_config


def _generate_statistics_summary(
    compliance_data: list[ComplianceReport],
    report: ComplianceReport,
    line: str,
    config_type: t.Literal["actual", "intended"] = "actual",
):
    if config_type == "actual":
        have_column = "Have This Line"
    else:
        have_column = "Don't Have this line (but should)"

    tab = Table(title="Statistics")
    tab.add_column("Statistic")
    tab.add_column("Out of Total")
    tab.add_column(have_column)

    def row(title, key):
        out_of_total = [r for r in compliance_data if getattr(r.device, key) == getattr(report.device, key)]
        out_of_total_count = f"{len(out_of_total)}/{len(compliance_data)}"
        out_of_total_percent = f"({len(out_of_total) / len(compliance_data) * 100:.2f}%)"

        have_this_line = [r for r in out_of_total if line in getattr(r, config_type).splitlines()]
        have_this_line_count = f"{len(have_this_line)}/{len(out_of_total)}"
        have_this_line_percent = f"({len(have_this_line) / len(out_of_total) * 100:.2f}%)"
        tab.add_row(
            f"Devices with matching {title} ({getattr(report.device, key)})",
            out_of_total_count + out_of_total_percent,
            have_this_line_count + have_this_line_percent,
        )

    # calculate percentage of devices with matching status
    row("status", "status")

    # calculate percentage of devices with matching version
    if report.device.software_version:
        row("version", "software_version")

    # calculate percentage of devices with matching device type
    row("device type", "device_type")

    # calculate percentage of devices with matching platform
    row("platform", "platform")

    return tab


def explore_compliance(feature: str):
    """
    Interactively explores compliance reports for a given feature.
    This function retrieves compliance data for the specified feature and iterates through each report that
    is not in compliance.
    For each non-compliant report, it displays a comparison table and prompts the user to explore either the
    "actual" (left) or "intended" (right) configuration differences.
    The user can select a specific line to further investigate, view a summary of statistics for that line,
    and optionally see a list of devices with matching configuration lines.
    The process continues for each non-compliant report.
    Args:
        feature: The name of the feature for which compliance data should be explored.
    Side Effects:
        - Prints tables and prompts to the console for interactive exploration.
        - Waits for user input to proceed through reports and options.
    """

    compliance_data = get_compliance_data(feature)
    con = console()
    for report in compliance_data:
        if report.in_compliance:
            continue
        report_config_table, extra_config, missing_config = _generate_report_comparison_table(report)
        con.print(report_config_table)
        side = Prompt.ask(
            "Do you want to explore the left or right (l/r) side of this report? Press enter to skip to next report",
            console=con,
            choices=["l", "r", ""],
        )
        if side:
            line_number = IntPrompt.ask("Enter the line number you want to explore")
            if side == "l":
                config_type = "actual"
                line = extra_config[line_number - 1]
            else:
                config_type = "intended"
                line = missing_config[line_number - 1]

            stats_table = _generate_statistics_summary(compliance_data, report, line, config_type=config_type)
            con.print(stats_table)

            if Confirm.ask("Do you want to see a list of devices with matching line?"):
                devices_report = _devices_with_matching_line(line, compliance_data, config_type=config_type)
                con.print(devices_report)
            input("Press enter to continue...")


def get_or_assign_oob_ip(switch_hostname: str, dev: bool = False) -> str:
    nb = get_api(dev=dev)
    switch = nb.dcim.devices.get(name=switch_hostname)
    switch = t.cast(NautobotDeviceRecord, switch)
    if not switch:
        raise Exception(f"Switch {switch_hostname} not found in Nautobot")

    mgmt_intf = nb.dcim.interfaces.get(device=switch.id, name="Management1")
    if not mgmt_intf:
        raise Exception(f"Switch {switch_hostname} does not have a Management1 interface")
    mgmt_intf = t.cast("Record", mgmt_intf)
    if not mgmt_intf.enabled:
        logger.info(f"Enabling Management1 interface on {switch_hostname}")
        mgmt_intf.update(dict(enabled=True))

    # intf role
    if mgmt_intf.role is None or mgmt_intf.role.name == "Management":
        logger.info(f"Setting Management1 interface role to Management on {switch_hostname}")
        role = nb.extras.roles.get(name="Management")
        mgmt_intf.update(dict(role=role))

    if len(mgmt_intf.ip_addresses) == 0:  # pyright: ignore[reportArgumentType]
        logger.warning(f"Switch {switch_hostname} does not have an OOB IP address assigned")
        oob_pfx = nb.ipam.prefixes.get(prefix="192.168.64.0/22")
        logger.warning(f"Assigning next available IP to {switch_hostname}")
        oob_ip = oob_pfx.available_ips.create(  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
            data=dict(
                status="Active",
                dns_name=f"{switch_hostname}-oob",
                description=f"{switch_hostname}-oob",
            )
        )
        nb.ipam.ip_address_to_interface.create(dict(ip_address=oob_ip.id, interface=mgmt_intf.id))  # type: ignore
        switch.update(dict(primary_ip4=oob_ip.id))  # type: ignore
        logger.info(f"Assigned IP {oob_ip.address} to {switch_hostname}")
    else:
        oob_ip = t.cast(list["Record"], mgmt_intf.ip_addresses)[0]  # type: ignore

    return oob_ip.address  # pyright: ignore[reportReturnType]


def latest_backup_job_succeeded():
    nb = get_api(dev=False)
    latest_backup_job = nb.extras.job_results.filter(
        name="nautobot_golden_config.jobs.BackupJob", sort="~date_created"
    )[0]
    succeeded = latest_backup_job.status.value != "FAILURE"  # pyright: ignore
    return succeeded, latest_backup_job


def _debug():
    latest_backup_job_succeeded()
