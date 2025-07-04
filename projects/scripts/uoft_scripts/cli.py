import sys
import typing as t
from enum import Enum

from .ldap.cli import app as ldap_app
from .nautobot.cli import app as nautobot_app
from .librenms.cli import app as librenms_app
from .sib_turnup.cli import app as sib_turnup_app
from .stg_ipam_dev.cli import app as stg_ipam_dev_app
from .arista.cli import app as arista_app

from uoft_core import logging

import typer


logger = logging.getLogger(__name__)

DEBUG_MODE = False

def _version_callback(value: bool):
    if not value:
        return
    from . import __version__
    import sys

    print(
        f"uoft-scripts v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="scripts",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)
app.add_typer(ldap_app)
app.add_typer(nautobot_app)
app.add_typer(librenms_app)
app.add_typer(sib_turnup_app)
app.add_typer(stg_ipam_dev_app)
app.add_typer(arista_app)


@app.callback()
def callback(
    version: t.Annotated[
        t.Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version information and exit"),
    ] = None,
    debug: bool = typer.Option(False, help="Turn on debug logging", envvar="DEBUG"),
    trace: bool = typer.Option(False, help="Turn on trace logging. implies --debug", envvar="TRACE"),
):
    global DEBUG_MODE
    log_level = "INFO"
    if debug:
        log_level = "DEBUG"
        DEBUG_MODE = True
    if trace:
        log_level = "TRACE"
        DEBUG_MODE = True
    logging.basicConfig(level=log_level)

class DeviceType(str, Enum):
    autodetect = "autodetect"
    cisco_ios = "cisco_ios"
    arista_eos = "arista_eos"
    aruba_aoscx = "aruba_aoscx"

@app.command()
def rename_switch(
    ip_address: str,
    old_name: str,
    new_name: str,
    device_type: DeviceType = DeviceType.autodetect,
):
    """
    Rename a switch in Nautobot, LibreNMS, Bluecat, and via SSH
    """
    logger.info(f"Renaming {old_name} to {new_name}")
    device_type_name = device_type.value # type: ignore
    from uoft_librenms import Settings as LibreNMSSettings
    from .nautobot import Settings as NautobotSettings
    from uoft_bluecat import Settings as BluecatSettings
    from uoft_ssh import Settings as SSHSettings
    from netmiko import ConnectHandler, SSHDetect
    from uoft_ssh.util import register_aoscx
    from pynautobot.models.extras import Record

    register_aoscx()

    logger.info("Changing name in LibreNMS...")
    lnms = LibreNMSSettings.from_cache().api_connection()
    lnms.devices.rename_device(
        device=f"{old_name}.netmgmt.utsc.utoronto.ca", new_hostname=f"{new_name}.netmgmt.utsc.utoronto.ca"
    )
    logger.success("Changed name in LibreNMS")

    logger.info("Changing name in Nautobot...")
    nautobot = NautobotSettings.from_cache().api_connection()
    nb_dev = t.cast("Record", nautobot.dcim.devices.get(name=old_name))
    nb_dev.name = new_name  # pyright: ignore[reportAttributeAccessIssue]
    nb_dev.save()
    logger.success("Changed name in Nautobot")

    logger.info("Changing name in Bluecat address and host record(s)...")
    with BluecatSettings.from_cache().alt_api_connection() as bluecat:
        bc_addr = bluecat.get("/addresses/", params=dict(filter=f"address:'{ip_address}'")).json()["data"][0]
        bc_addr["name"] = new_name
        bluecat.put(f"/addresses/{bc_addr['id']}", json=bc_addr, comment=f"Renaming {old_name} to {new_name}")
        host_records = bluecat.get(
            "/resourceRecords/",
            params=dict(filter=f"absoluteName:'{old_name}.netmgmt.utsc.utoronto.ca'"),
        ).json()["data"]
        for bc_host_record in host_records:
            bc_host_record["name"] = new_name
            bluecat.put(
                f"/resourceRecords/{bc_host_record['id']}",
                json=bc_host_record,
                comment=f"Renaming {old_name} to {new_name}",
            )
    logger.success("Changed name in Bluecat. Don't forget to deploy changes to DNS servers!")

    logger.info("changing device's own hostname through SSH...")
    ssh_s = SSHSettings.from_cache()
    ssh_c = dict(
        device_type=device_type_name,
        ip=ip_address,
        username=ssh_s.personal.username,
        password=ssh_s.personal.password.get_secret_value(),
        secret=ssh_s.enable_secret.get_secret_value(),
    )
    if device_type_name == "autodetect":
        guesser = SSHDetect(**ssh_c)
        device_type_name = t.cast(str, guesser.autodetect())
        ssh_c["device_type"] = device_type_name
    with ConnectHandler(**ssh_c) as ssh:
        ssh.send_config_set(config_commands=[f'hostname {new_name}'])
        ssh.send_command("write memory")
        logger.success("Changed device's hostname through SSH")

    logger.success(f"Renamed {old_name} to {new_name}")


@app.command()
def update_switch_intf_configs(
    switch_hostname: t.Annotated[
        str, typer.Argument(help="Hostname of the switch to update interface configs for", metavar="HOSTNAME")
    ],
    intf_names: t.Annotated[
        list[str],
        typer.Argument(help="List of interface names to update on the switch", metavar="INTF_NAME..."),
    ],
):
    """
    Given a switch hostname and a list of interface names,
    update the interface configurations on the switch
    to match the intended config from Nautobot.
    """
    from . import update_switch_intf_configs

    update_switch_intf_configs(switch_hostname, *intf_names)


def cli():
    try:
        # CLI code goes here
        app()
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()
    except Exception as e:
        if DEBUG_MODE:
            raise
        logger.error(e)
        sys.exit(1)


def deprecated():
    import sys
    from warnings import warn

    cmdline = " ".join(sys.argv)
    if (from_ := "uoft_scripts") in cmdline:
        to = "uoft-scripts"
        cmd = app
    elif (from_ := "utsc.scripts") in cmdline:
        to = "uoft-scripts"
        cmd = app
    elif (from_ := "utsc.scripts aruba") in cmdline:
        to = "uoft-aruba"
        from uoft_aruba.cli import app as aruba_app

        cmd = aruba_app
    else:
        raise ValueError(f"command {cmdline} is not deprecated")

    # TODO: convert this into a log.warn msg once we've sorted out logging
    warn(FutureWarning(f"The '{from_}' command has been renamed to '{to}' and will be removed in a future version."))
    cmd()


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    print()


if __name__ == "__main__":
    cli()
