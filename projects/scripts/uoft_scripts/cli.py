import sys
from typing import Annotated, Optional
from enum import Enum

from . import ldap
from . import nautobot
from . import librenms
from . import sib_turnup

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
app.add_typer(ldap.app)
app.add_typer(nautobot.app)
app.add_typer(librenms.app)
app.add_typer(sib_turnup.app)


@app.callback()
def callback(
    version: Annotated[
        Optional[bool],
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
    device_type = device_type.value # type: ignore
    from uoft_librenms import Settings as LibreNMSSettings
    from .nautobot import Settings as NautobotSettings
    from uoft_bluecat import Settings as BluecatSettings
    from uoft_ssh import Settings as SSHSettings
    from netmiko import ConnectHandler, SSHDetect
    from uoft_ssh.util import register_aoscx

    register_aoscx()

    logger.info("Changing name in LibreNMS...")
    lnms = LibreNMSSettings.from_cache().api_connection()
    lnms.devices.rename_device(
        device=f"{old_name}.netmgmt.utsc.utoronto.ca", new_hostname=f"{new_name}.netmgmt.utsc.utoronto.ca"
    )
    logger.success("Changed name in LibreNMS")

    logger.info("Changing name in Nautobot...")
    nautobot = NautobotSettings.from_cache().api_connection()
    nb_dev = nautobot.dcim.devices.get(name=old_name)
    nb_dev.name = new_name # type: ignore
    nb_dev.save() # type: ignore
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
        device_type=device_type,
        ip=ip_address,
        username=ssh_s.personal.username,
        password=ssh_s.personal.password.get_secret_value(),
        secret=ssh_s.enable_secret.get_secret_value(),
    )
    if device_type == "autodetect":
        guesser = SSHDetect(**ssh_c)
        device_type = guesser.autodetect() # type: ignore
        ssh_c["device_type"] = device_type
    with ConnectHandler(**ssh_c) as ssh:
        ssh.send_config_set(config_commands=[f'hostname {new_name}'])
        ssh.send_command("write memory")
        logger.success("Changed device's hostname through SSH")

    logger.success(f"Renamed {old_name} to {new_name}")


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
