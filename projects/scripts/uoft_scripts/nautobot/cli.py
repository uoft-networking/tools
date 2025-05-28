import typing as t
from pathlib import Path

from uoft_core import logging

from . import OnOrphanAction, ComplianceReportGoal

import typer

app = typer.Typer(name="nautobot")

logger = logging.getLogger(__name__)


def _validate_templates_dir(templates_dir):
    if templates_dir is None:
        templates_dir = Path(".")
    if not templates_dir.joinpath("filters.py").exists():
        logger.error(f"Expected to find a `filters.py` file in template repo directory '{templates_dir.resolve()}'")
        logger.warning("Are you sure you're in the right directory?")
        raise typer.Exit(1)
    return templates_dir


def _autocomplete_hostnames(ctx: typer.Context, partial: str):
    from . import get_api
    from pynautobot.models.extras import Record

    dev = ctx.params.get("dev", False)
    nb = get_api(dev)
    if partial:
        query = nb.dcim.devices.filter(name__ic=partial)
    else:
        query = nb.dcim.devices.all()
    query = t.cast(list[Record], query)
    return [d.name for d in query]


def _assert_cwd_is_devicetype_library():
    if not (Path(".git").exists() and Path("device-types").exists()):
        logger.error(
            "This command is meant to be run from within the device-type-library repository. "
            "Please clone the repository from https://github.com/netbox-community/devicetype-library"
            " and run this command from within the repository folder."
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


TemplatesPath: t.TypeAlias = t.Annotated[Path, typer.Option(exists=True, callback=_validate_templates_dir)]


@app.command()
def sync_from_bluecat(dev: bool = False, interactive: bool = True, on_orphan: OnOrphanAction = OnOrphanAction.prompt):
    from . import lib

    lib.sync_from_bluecat(
        dev=dev,
        interactive=interactive,
        on_orphan=on_orphan,
    )


@app.command()
def show_golden_config_data(
    device_name: str = typer.Argument(..., autocompletion=_autocomplete_hostnames),
    dev: bool = False,
):
    """
    Show the golden config data for a device.
    """
    from . import lib

    lib.show_golden_config_data(device_name, dev=dev)


@app.command()
def trigger_golden_config_intended(
    device_name: t.Annotated[str, typer.Argument(..., autocompletion=_autocomplete_hostnames)],
    dev: bool = False,
):
    """
    Trigger the generation of intended config for a device.
    """
    from . import lib

    lib.trigger_golden_config_intended(device_name, dev=dev)


@app.command()
def template_filter_info(
    templates_dir: TemplatesPath = Path("."),
):
    """
    Show information about the template filters available in the specified directory.

    Args:
        templates_dir (Path): The directory containing the template filters.
    """
    templates_dir = _validate_templates_dir(templates_dir)
    from . import lib

    lib.template_filter_info(templates_dir)


@app.command()
def test_golden_config_templates(
    device_name: t.Annotated[str, typer.Argument(autocompletion=_autocomplete_hostnames)],
    override_status: str | None = None,
    templates_dir: TemplatesPath = Path("."),
    dev: bool = False,
    print_output: bool = True,
):
    """
    Test the golden config templates for a device.

    Args:
        device_name (str): The name of the device to test.
        override_status (str | None): Override the status of the job. If None, the job will run normally.
        templates_dir (Path): The directory containing the template filters.
        dev (bool): Whether to use the development environment.
        print_output (bool): Whether to print the output of the test.
    """
    from . import lib

    templates_dir = _validate_templates_dir(templates_dir)
    lib.test_golden_config_templates(
        device_name=device_name,
        override_status=override_status,
        templates_dir=templates_dir,
        dev=dev,
        print_output=print_output,
    )


@app.command()
def push_changes_to_nautobot(
    templates_dir: TemplatesPath = Path("."),
    dev: bool = False,
):
    from . import lib

    templates_dir = _validate_templates_dir(templates_dir)
    lib.push_changes_to_nautobot(templates_dir, dev=dev)


@app.command()
def test_templates_in_nautobot(
    templates_dir: TemplatesPath = Path("."),
    dev: bool = False,
):
    from . import lib

    templates_dir = _validate_templates_dir(templates_dir)
    lib.test_templates_in_nautobot(templates_dir, dev=dev)


@app.command()
def device_type_add_or_update(
    dev: bool = False,
):
    """
    Add or update device types in Nautobot from the device-type-library repository.

    This command will scan the device-type-library repository for new or updated device types
    and add or update them in Nautobot.

    Args:
        dev (bool): Whether to use the development environment.
    """
    from . import lib

    # check to make sure this command is being run from within the device-types library repo
    _assert_cwd_is_devicetype_library()

    lib.device_type_add_or_update(dev=dev)


@app.command()
def new_switch(
    dev: bool = False,
):
    """
    Create a new switch in Nautobot.

    This command will create a new switch in Nautobot with the necessary configurations.
    It will prompt for the device type and other required information.
    """
    from . import lib

    lib.new_switch(dev=dev)


@app.command()
def regen_interfaces(
    device_name: t.Annotated[str, typer.Argument(autocompletion=_autocomplete_hostnames)],
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
    from . import lib

    lib.regen_interfaces(device_name, dev=dev)


@app.command()
def rebuild_switch(
    set_status_to_planned: bool = False,
    dev: bool = False,
):
    """
    Rebuild a switch in Nautobot against a new device type

    This script would be useful if, for example, you're replacing a switch with a newer model,
    while keeping the hostname and ip address the same.
    """
    from . import lib

    lib.rebuild_switch(set_status_to_planned=set_status_to_planned, dev=dev)


@app.command()
def generate_compliance_commands(
    feature: t.Annotated[str, typer.Option(help='The compliance feature to process. Defaults to "base"')] = "base",
    goal: t.Annotated[
        ComplianceReportGoal,
        typer.Option(help="The compliance goal, either to add missing config or remove extra config"),
    ] = ComplianceReportGoal.add,
    filters: t.Annotated[
        list[str] | None, typer.Option(help="List of string filters to apply to the configuration commands")
    ] = None,
    sub_filters: t.Annotated[
        list[str] | None, typer.Option(help="List of sub-filters to further refine the configuration commands")
    ] = None,
    merge_with: t.Annotated[
        Path | None, typer.Option(help="Path to a JSON file to merge the generated commands with existing data")
    ] = None,
    top_level_only: t.Annotated[
        bool, typer.Option(help="If True, only top-level configuration commands are considered")
    ] = False,
    prefix_when_merging: t.Annotated[
        bool, typer.Option(help="If True, new commands are prefixed when merging with existing data")
    ] = False,
):
    """
    Generate compliance commands for network devices based on compliance reports.
    This function processes compliance data for a specified feature and generates the necessary configuration commands
    to either add missing configuration or remove extra configuration from devices. The commands can be filtered,
    flattened, and optionally merged with existing data in a JSON file.

    Prints the generated commands as a JSON object if `merge_with` is not provided.
    If `merge_with` is provided, updates the specified JSON file with the merged commands.
    """
    from . import lib

    lib.generate_compliance_commands(
        feature=feature,
        goal=goal,
        filters=filters,
        sub_filters=sub_filters,
        merge_with=merge_with,
        top_level_only=top_level_only,
        prefix_when_merging=prefix_when_merging,
    )


@app.command()
def explore_compliance(
    feature: t.Annotated[
        str, typer.Option(help="The name of the feature for which compliance data should be explored")
    ],
):
    """
    Interactively explores compliance reports for a given feature.
    This function retrieves compliance data for the specified feature and iterates through each report that 
    is not in compliance.
    For each non-compliant report, it displays a comparison table and prompts the user to explore either the 
    "actual" (left) or "intended" (right) configuration differences.
    The user can select a specific line to further investigate, view a summary of statistics for that line, 
    and optionally see a list of devices with matching configuration lines.
    The process continues for each non-compliant report.

    Prints tables and prompts to the console for interactive exploration.
    Waits for user input to proceed through reports and options.
    """
    from . import lib

    lib.explore_compliance(feature)
