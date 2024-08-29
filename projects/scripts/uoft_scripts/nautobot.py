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
import typing

from uoft_core.types import IPNetwork, IPAddress, BaseModel, SecretStr
from uoft_core import logging
from uoft_core import BaseSettings, Field, StrEnum

import pynautobot
import pynautobot.core.endpoint
from pynautobot.core.response import Record
import deepdiff
import deepdiff.model
import typer
import jinja2
from uoft_core.console import console


class Settings(BaseSettings):
    """Settings for the nautobot_cli application."""

    url: str = Field(..., title="Nautobot server URL")
    token: SecretStr = Field(..., title="Nautobot API Token")

    class Config(BaseSettings.Config):
        app_name = "nautobot-cli"

    def api_connection(self):
        return pynautobot.api(url=self.url, token=self.token.get_secret_value())


class DevSettings(Settings):
    class Config(BaseSettings.Config):
        app_name = "nautobot-cli-dev"

def get_settings(dev: bool = False):
    if dev:
        return DevSettings.from_cache()
    return Settings.from_cache()

logger = logging.getLogger(__name__)

app = typer.Typer(name="nautobot")

ip_address: typing.TypeAlias = str
"ip address in CIDR notation, e.g. '192.168.0.20/24'"
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


class DeviceModel(BaseModel):
    hostname: str
    ip_address: ip_address


Prefixes: typing.TypeAlias = dict[network_prefix, PrefixModel]
Addresses: typing.TypeAlias = dict[ip_address, IPAddressModel]
Devices: typing.TypeAlias = dict[str, DeviceModel]


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
        self.syncdata = None  # type: ignore
        self.diff = None  # type: ignore

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
        assert (
            set(diff.keys()) <= expected_diff_types
        ), f"Deepdiff has identified unexpected type[s] of change: {set(diff.keys()) - expected_diff_types}"

        delta = deepdiff.Delta(diff)

        new_syncdata: SyncData = self.syncdata + delta  # type: ignore

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
    for record in diff.tree[change_type_name]:  # type: ignore
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


def _validate_templates_dir(templates_dir):
    if templates_dir is None:
        templates_dir = Path(".")
    if not templates_dir.joinpath("filters.py").exists():
        logger.error(f"Expected to find a `filters.py` file in template repo directory '{templates_dir.resolve()}'")
        logger.warning("Are you sure you're in the right directory?")
        raise typer.Exit(1)
    return templates_dir


TemplatesPath: typing.TypeAlias = typing.Annotated[Path, typer.Option(exists=True, callback=_validate_templates_dir)]


class OnOrphanAction(StrEnum):
    prompt = "prompt"
    delete = "delete"
    backport = "backport"
    skip = "skip"


@app.command()
def sync_from_bluecat(dev: bool = False, interactive: bool = True, on_orphan: OnOrphanAction = OnOrphanAction.prompt):
    from uoft_core import Timeit
    from . import _sync

    print = console().print

    t = Timeit()

    def done():
        runtime = t.stop().str
        print(f"Sync completed in {runtime}")

    datasets = {"prefixes", "addresses"}
    bc = _sync.BluecatTarget()
    nb = _sync.NautobotTarget(dev=dev)
    sm = _sync.SyncManager(bc, nb, datasets, on_orphan=on_orphan.value)  # type: ignore

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


def _autocomplete_hostnames(ctx: typer.Context, partial: str):
    dev = ctx.params.get("dev", False)
    nb = get_settings(dev).api_connection()
    if partial:
        query = nb.dcim.devices.filter(name__ic=partial)
    else:
        query = nb.dcim.devices.all()
    return [d.name for d in query]  # type: ignore


def _autocomplete_manufacturers(ctx: typer.Context, partial: str):
    dev = ctx.params.get("dev", False)
    nb = get_settings(dev).api_connection()
    if partial:
        query = nb.dcim.manufacturers.filter(name__ic=partial)
    else:
        query = nb.dcim.manufacturers.all()
    return [d.name for d in query]  # type: ignore


def _autocomplete_device_types(ctx: typer.Context, partial: str):
    dev = ctx.params.get("dev", False)
    mfg = ctx.params.get("manufacturer", None)
    nb = get_settings(dev).api_connection()
    if mfg:
        mfg_id = nb.dcim.manufacturers.get(name=mfg).id  # type: ignore
        if partial:
            query = nb.dcim.device_types.filter(manufacturer=mfg_id, model__ic=partial)
        else:
            query = nb.dcim.device_types.filter(manufacturer=mfg_id)
    else:
        if partial:
            query = nb.dcim.device_types.filter(model__ic=partial)
        else:
            query = nb.dcim.device_types.all()
    return [d.model for d in query]  # type: ignore


def _get_jinja_env(templates_dir: Path):
    from . import _jinja
    from uoft_core import jinja_library

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    _jinja.import_repo_filters_module(templates_dir)
    # the _jinja module registers filters when it's imported,
    # and the templates_dir's filters.py file registers filters / functions / extensions when it's imported
    # we need to update the environment with the filters / functions / extensions from both
    jinja_library._update_env(env)
    return env


@app.command()
def show_golden_config_data(
    device_name: str = typer.Argument(..., autocompletion=_autocomplete_hostnames),
    dev: bool = False,
):
    nb = get_settings(dev).api_connection()
    device: Record = nb.dcim.devices.get(name=device_name)  # type: ignore
    gql_query: str = nb.extras.graphql_queries.get(name="golden_config").query  # type: ignore
    data = nb.graphql.query(gql_query, {"device_id": device.id})
    print(json.dumps(data.json["data"]["device"], indent=2))


@typing.no_type_check
@app.command()
def trigger_golden_config_intended(
    device_name: typing.Annotated[str, typer.Argument(..., autocompletion=_autocomplete_hostnames)],
    dev: bool = False,
):
    nb = get_settings(dev).api_connection()
    device: Record = nb.dcim.devices.get(name=device_name)
    job = nb.extras.jobs.get(name="Generate Intended Configurations")
    job_result = nb.extras.jobs.run(job_id=job.id, data={"device": [device.id]}).job_result
    print(
        "A new `Generate Intended Configurations` job run has been triggered. Job status / results can be found here:"
    )
    print(job_result.url.replace("/api/", "/"))


@app.command()
def template_filter_info(
    templates_dir: TemplatesPath = Path("."),
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
    env = _get_jinja_env(templates_dir)
    filters = [f for f in env.filters]
    filters = sorted(filters)
    filters = "\n- ".join(filters)
    logger.info(f"You have the following filters available: \n- {filters}")


@app.command()
def test_golden_config_templates(
    device_name: typing.Annotated[str, typer.Argument(autocompletion=_autocomplete_hostnames)],
    templates_dir: TemplatesPath = Path("."),
    dev: bool = False,
    print_output: bool = True,
):
    nb = get_settings(dev).api_connection()
    device: Record|None = nb.dcim.devices.get(name=device_name)  # type: ignore
    if not device:
        logger.error(f"Device {device_name} not found in Nautobot")
        raise typer.Exit(1)
    gql_query = templates_dir.joinpath("graphql/golden_config.graphql").read_text()
    data = nb.graphql.query(gql_query, {"device_id": device.id}).json["data"]["device"]

    # we need to copy the behaviour of the transposer function without actually importing it
    data["data"] = data.copy()

    # we need to set up a jinja environment which mimics the behaviour of the one set up by
    # nautobot for rendering golden config templates
    env = _get_jinja_env(templates_dir)
    t = env.get_template("templates/entrypoint.j2")
    text = t.render(data)
    if print_output:
        print(text)
    return text


@typing.no_type_check
@app.command()
def push_changes_to_nautobot(
    templates_dir: TemplatesPath = Path("."),
    dev: bool = False,
):
    import subprocess

    # make sure git status is clean
    git_status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, cwd=templates_dir)
    assert git_status.returncode == 0, "This command is meant to be run AFTER you've committed your changes."

    logger.info("Pushing local changes to gitlab")
    subprocess.run(["git", "push"], check=True, cwd=templates_dir)

    logger.info("Telling nautobot to pull the changes")
    nb = get_settings(dev).api_connection()
    gitrepo = nb.extras.git_repositories.get(name="golden_config_templates")
    job = nb.extras.jobs.get(name="Git Repository: Sync")
    job_result = nb.extras.jobs.run(job_id=job.id, data={"repository": gitrepo.id}).job_result
    print("A new `GitRepository: Sync` job run has been triggered. Job status / results can be found here:")
    print(job_result.url.replace("/api/", "/"))


def _assert_cwd_is_devicetype_library():
    if not (Path(".git").exists() and Path("device-types").exists()):
        logger.error(
            "This command is meant to be run from within the device-type-library repository. "
            "Please clone the repository from https://github.com/netbox-community/devicetype-library"
            "and run this command from within the repository folder."
        )
        raise typer.Exit(1)


def _complete_mfg(incomplete: str):
    _assert_cwd_is_devicetype_library()
    if incomplete:
        search_space = Path("device-types").glob(f"{incomplete}*")
    else:
        search_space = Path("device-types").iterdir()
    for dir in search_space:
        if dir.is_dir():
            yield dir.name


def _complete_model(incomplete: str, ctx: typer.Context):
    _assert_cwd_is_devicetype_library()
    manufacturer = ctx.params["manufacturer"]
    search_space = Path("device-types").joinpath(manufacturer).glob(f"{incomplete}*.yaml")
    for file in search_space:
        yield file.stem  # stem instead of name, because we don't want the .yaml extension


def _device_family_id(nb, prompt, model):
    device_families_by_name = {}
    for family in nb.dcim.device_families.all():
        device_families_by_name[family.name] = family.id  # type: ignore

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
            return family.id  # type: ignore
        else:
            return device_families_by_name[family_name]


def _manufacturer_id(nb, manufacturer):
    mfg = nb.dcim.manufacturers.get(name=manufacturer)
    if not mfg:
        logger.info(f"Manufacturer {manufacturer} not found, creating...")
        mfg = nb.dcim.manufacturers.create(name=manufacturer)
    return mfg.id  # type: ignore


@app.command()
def device_type_add_or_update(
    manufacturer: typing.Annotated[str, typer.Argument(autocompletion=_complete_mfg)],
    model: typing.Annotated[str, typer.Argument(autocompletion=_complete_model)],
    dev: bool = False,
):
    """
    create or update a device type in nautobot based on a device type file in the device-types repo
    """

    # check to make sure this command is being run from within the device-types library repo
    _assert_cwd_is_devicetype_library()

    # make sure the specified manufacturer and model exist in the device-types library
    device_type_file = Path("device-types").joinpath(manufacturer, f"{model}.yaml")
    assert device_type_file.exists(), f"Device type file not found: {device_type_file}"

    # read the device type file
    from uoft_core.yaml import loads

    device_type = loads(device_type_file.read_text())

    prompt = Settings._prompt()

    nb = get_settings(dev).api_connection()

    # the device_type dictionary ALMOST perfectly matches the structure expected by the Nautobot API
    # for device_types
    model = device_type["model"]

    if existing_device_type := nb.dcim.device_types.get(model=model, manufacturer=device_type["manufacturer"]):
        logger.info(f"Device type {model} already exists in Nautobot")
        if not prompt.get_bool(
            "update_device_type",
            "Would you like to update this device type?",
        ):
            return
        device_type_id = existing_device_type.id  # type: ignore
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

        res = nb.dcim.device_types.create(nb_data)
        device_type_id = res.id  # type: ignore

    logger.info(f"Device type {model} created with id {device_type_id}")

    def _populate_interface(interface):
        interface_data = dict(
            device_type=device_type_id,
            name=interface.get("name"),
            type=interface.get("type"),
            mgmt_only=interface.get("mgmt_only"),
            description=interface.get("description"),
        )
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

    def _populate_console_port(console_port):
        console_port_data = dict(
            device_type=device_type_id,
            name=console_port.get("name"),
            type=console_port.get("type"),
            description=console_port.get("description"),
        )
        if console_port_data["description"] is None:
            del console_port_data["description"]
        try:
            nb.dcim.console_port_templates.create(console_port_data)
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all console ports
            # will already exist. in this case, we can ignore the error
            pass

    def _populate_power_port(power_port):
        power_port_data = dict(
            device_type=device_type_id,
            name=power_port.get("name"),
            type=power_port.get("type"),
            description=power_port.get("description"),
        )
        if power_port_data["description"] is None:
            del power_port_data["description"]
        try:
            nb.dcim.power_port_templates.create(power_port_data)
        except pynautobot.RequestError:
            # in case of updating an existing device type, some or all power ports
            # will already exist. in this case, we can ignore the error
            pass

    def _populate_module_bay(module_bay):
        mb_name = module_bay.get("name")
        if prompt.get_bool(
            "load_module",
            f"{model} defines a module bay called {mb_name}. " "Would you like to link a module into it?",
        ):
            modules_available = [f.stem for f in Path("module-types").joinpath(manufacturer).glob("*.yaml")]
            module_file_name = prompt.get_from_choices(
                "module",
                modules_available,
                "Select a module to link to this module bay",
            )
            module_file = Path("module-types").joinpath(manufacturer, f"{module_file_name}.yaml")
            module_data = loads(module_file.read_text())
            _populate_device_type_components(module_data)

    def _populate_device_type_components(component_data):
        # component_data could be the device_type dict,
        # or it could be a dict loaded from a module
        if interfaces := component_data.get("interfaces"):
            logger.info(f"Creating interfaces for {model}")
            for interface in interfaces:
                _populate_interface(interface)

        if console_ports := component_data.get("console-ports"):
            logger.info(f"Creating console ports for {model}")
            for console_port in console_ports:
                _populate_console_port(console_port)

        if power_ports := component_data.get("power-ports"):
            logger.info(f"Creating power ports for {model}")
            for power_port in power_ports:
                _populate_power_port(power_port)

        if "rear-ports" in component_data or "front-ports" in component_data:
            # TODO: add support for front and rear ports to support patch panels
            logger.error(
                f"{model} defines rear-ports or front-ports, which are not yet supported by this script. Skipping..."
            )
            logger.error("Please create these manually in Nautobot or ask my creator to add support for them.")

        if module_bays := component_data.get("module-bays"):
            for module_bay in module_bays:
                _populate_module_bay(module_bay)

    _populate_device_type_components(device_type)

    logger.info("Done!")


@app.command()
def new_switch(
    dev: bool = False,
):
    """
    Create a new switch in Nautobot

    This script prompts you for info and creates a new switch entry for you in nautobot
    """
    prompt = Settings._prompt()
    nb = get_settings(dev).api_connection()

    def _select_from_queryset(
        queryset,
        name,
        msg,
        key="name",
        create_new_callback: typing.Callable | None = None,
        **kwargs,
    ):
        mapping: dict[str, str] = {obj[key]: obj["id"] for obj in queryset}
        choices = list(mapping.keys())
        if create_new_callback:
            choices = ["Create a new one...", *choices]
        choice = prompt.get_from_choices(
            name,
            list(mapping.keys()),
            msg,
            completer_opts=dict(ignore_case=True),
            **kwargs,
        )
        if create_new_callback and choice == "Create a new one...":
            return create_new_callback()
        return choice, mapping[choice]

    name = prompt.get_string("name", "Enter the name of the switch")

    logger.info("Loading list of available Manufacturers from Nautobot...")
    manufacturer, manufacturer_id = _select_from_queryset(
        nb.dcim.manufacturers.all(),
        "manufacturer",
        "Select a manufacturer for this switch",
    )

    logger.info(f"Loading list of available {manufacturer} Device Types from Nautobot...")
    dt, dt_id = _select_from_queryset(
        nb.dcim.device_types.filter(manufacturer=manufacturer_id),
        "device_type",
        "Select a device type for this switch",
        key="model",
        fuzzy_search=True,
    )

    platform, platform_id = _select_from_queryset(
        nb.dcim.platforms.filter(manufacturer=manufacturer_id),
        "platform",
        "Select a platform for this switch",
        fuzzy_search=True,
    )

    logger.info("Loading list of Device Roles from Nautobot...")
    role, role_id = _select_from_queryset(
        nb.extras.roles.filter(content_types="dcim.device"),
        "role",
        "What kind of switch are you creating?",
    )

    logger.info("Loading list of Locations from Nautobot...")
    locations: dict[str, str] = {obj["display"]: obj["id"] for obj in nb.dcim.locations.all()}  # type: ignore

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
        logger.info(f"Creating new location '{name}'...")
        location_record = nb.dcim.locations.create(
            name=location_name,
            location_type={"name": "Room"},
            parent=locations[building_name],
            status={"name": "Active"},
            custom_fields=dict(room_number=prompt.get_string("room_number", "Enter the room number (ex. AC290)")),
        )
        return location_name, location_record.id  # type: ignore

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

    vlan_groups = nb.ipam.vlan_groups.all()
    vlan_group_name = prompt.get_from_choices(
        "vlan_group",
        [vg.name for vg in vlan_groups],
        "Select a VLAN Group for this switch",
    )
    vlan_group = next(vg for vg in vlan_groups if vg.name == vlan_group_name)
    logger.info(f"Assigning VLAN Group {vlan_group_name} to {name}...")

    # Tags
    tags = []
    logger.info("Loading list of available device Tags from Nautobot...")
    available_tags: dict[str, str] = {
        tag["name"]: tag["id"]  # type: ignore
        for tag in nb.extras.tags.filter(content_types="dcim.device")
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
    if prompt.get_bool("override_os_version", "Would you like to override the OS version for this device?"):
        os_version = prompt.get_string("os_version", "Enter the OS version for this device")
        config_context["os_version"] = os_version

    logger.info("Checking to see if Device already exists in Nautobot...")
    if device := nb.dcim.devices.get(name=name):
        logger.info(f"Device {name} already exists in Nautobot, updating...")
        nb.dcim.devices.update(
            id=device.id,  # type: ignore
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
        device = nb.dcim.devices.create(
            name=name,
            device_type=dt_id,
            platform=platform_id,
            role=role_id,
            status="Planned",
            location=location_id,
            vlan_group=vlan_group.id,
            manufacturer=manufacturer_id,
            tags=tags,
        )

    logger.info(f"Checking to see if {name}/{interface_name} already exists in Nautobot...")
    mgmt_interface = nb.dcim.interfaces.get(device=device.id, name=interface_name)  # type: ignore
    if not mgmt_interface:
        logger.info(f"Creating primary interface {interface_name} for {name} in Nautobot...")
        mgmt_interface = nb.dcim.interfaces.create(
            device=device.id,  # type: ignore
            name=interface_name,
            type="virtual",
            status="Active",
        )

    logger.info(f"Checking to see if {primary_ip4} already exists in Nautobot...")
    if ipv4 := nb.ipam.ip_addresses.get(address=primary_ip4):
        logger.info(f"IP Address {primary_ip4} already exists in Nautobot, updating...")
        nb.ipam.ip_addresses.update(
            id=ipv4.id,  # type: ignore
            data=dict(
                status="Active",
                description=name,
                dns_name=f"{name}.netmgmt.utsc.utoronto.ca",
                address=primary_ip4,
            ),
        )
    else:
        logger.info(f"Creating new IP Address {primary_ip4} in Nautobot...")
        ipv4 = nb.ipam.ip_addresses.create(
            address=primary_ip4,
            status="Active",
            namespace={"name": "Global"},
            description=name,
            dns_name=f"{name}.netmgmt.utsc.utoronto.ca",
        )

    logger.info(f"Associating {primary_ip4} with {interface_name}...")
    try:
        nb.ipam.ip_address_to_interface.create(
            ip_address=ipv4.id,  # type: ignore
            interface=mgmt_interface.id,  # type: ignore
        )
    except pynautobot.RequestError as e:
        if "must make a unique set" in e.args[0]:
            logger.info(f"IP Address {primary_ip4} is already associated with {interface_name}")
        else:
            raise e

    logger.info(f"Assigning {primary_ip4} as Primary IP for {name}...")
    device.primary_ip4 = ipv4  # type: ignore

    device.save()  # type: ignore

    logger.info("Done!")


@app.command()
def regen_interfaces(
    device_name: typing.Annotated[str, typer.Argument(autocompletion=_autocomplete_hostnames)],
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
    nb = get_settings(dev).api_connection()
    device: Record = nb.dcim.devices.get(name=device_name)  # type: ignore
    device_type: Record = nb.dcim.device_types.get(id=device.device_type.id)  # type: ignore
    logger.info(f"Regenerating entries for {device_name} based on device type {device_type.model}")
    logger.info("Regenerating interfaces...")
    for i_t in nb.dcim.interface_templates.filter(device_type=device_type.id):
        nb.dcim.interfaces.create(
            device=device.id,
            name=i_t.name,  # type: ignore
            label=i_t.label,  # type: ignore
            type=i_t.type.value,  # type: ignore
            mgmt_only=i_t.mgmt_only,  # type: ignore
            description=i_t.description,  # type: ignore
            status="Active",
        )
    logger.info("Regenerating console ports...")
    for c_t in nb.dcim.console_port_templates.filter(device_type=device_type.id):
        nb.dcim.console_ports.create(
            device=device.id,
            name=c_t.name,  # type: ignore
            label=c_t.label,  # type: ignore
            type=c_t.type.value,  # type: ignore
            description=c_t.description,  # type: ignore
        )
    logger.info("Regenerating power ports...")
    for p_t in nb.dcim.power_port_templates.filter(device_type=device_type.id):
        nb.dcim.power_ports.create(
            device=device.id,
            name=p_t.name,  # type: ignore
            label=p_t.label,  # type: ignore
            type=p_t.type.value,  # type: ignore
            description=p_t.description,  # type: ignore
        )
    logger.success("Done")


@app.command()
def rebuild_switch(
    device_name: typing.Annotated[str, typer.Argument(autocompletion=_autocomplete_hostnames)],
    manufacturer: typing.Annotated[str, typer.Argument(autocompletion=_autocomplete_manufacturers)],
    device_type: typing.Annotated[str, typer.Argument(autocompletion=_autocomplete_device_types)],
    dev: bool = False,
):
    """
    Rebuild a switch in Nautobot against a new device type

    This script would be useful if, for example, you're replacing a switch with a newer model,
    while keeping the hostname and ip address the same.
    """
    prompt = Settings._prompt()
    nb = get_settings(dev).api_connection()
    device = nb.dcim.devices.get(name=device_name)
    if not device:
        logger.error(f"Device {device_name} not found in Nautobot")
        return
    manufacturer = nb.dcim.manufacturers.get(name=manufacturer)
    device_type = nb.dcim.device_types.get(model=device_type, manufacturer=manufacturer.id)
    platforms = nb.dcim.platforms.filter(manufacturer=manufacturer.id)
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
    logger.warning(f"This script will delete the following interfaces:")
    logger.info(old_interfaces)
    if not prompt.get_bool('delete_interfaces', 'Do you want to continue?'):
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
    device.device_type = device_type
    if platform:
        device.platform = platform

    device.save()
    # create new interfaces / console ports / power ports based on the new device type
    regen_interfaces(device_name, dev)
