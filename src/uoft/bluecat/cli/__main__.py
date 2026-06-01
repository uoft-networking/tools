"""
CLI and API to manage a Bluecat instance
"""

import sys
from typing import Annotated, Optional

import typer
from uoft.core import logging
from uoft.core.console import console

from ..conf import Settings

logger = logging.getLogger(__name__)

DEBUG_MODE = False


def _version_callback(value: bool):
    if not value:
        return
    from ..version import __version__
    import sys

    print(
        f"uoft-{Settings.Config.app_name} v{__version__} \nPython {sys.version_info.major}."
        f"{sys.version_info.minor} ({sys.executable}) on {sys.platform}"
    )
    raise typer.Exit()


app = typer.Typer(
    name="bluecat",
    context_settings={"max_content_width": 120, "help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help=__doc__,  # Use this module's docstring as the main program help text
)


@app.callback()
@Settings.wrap_typer_command
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


@app.command()
def get_all_prefixes():
    with Settings.from_cache().get_api_connection() as api:
        blocks = api.get("/blocks").json()["data"]
        nets = api.get("/networks").json()["data"]
    con = console()
    con.print(blocks)
    con.print(nets)


@app.command()
def add_or_update_ip(
    ip: Annotated[str, typer.Argument(help="IP address to add or update")],
    hostname: Annotated[str, typer.Argument(help="Hostname to add or update")],
):
    from uoft.core.types import IPAddress

    try:
        address = IPAddress(ip)
    except ValueError as e:
        logger.error(f"Invalid IP address: {ip}. Error: {e}")
        sys.exit(1)
    with Settings.from_cache().get_api_connection() as api:
        try:
            r = api.get_address(address)
        except ValueError:
            logger.info(f"Creating address {address}")
            r = api.create_address(address, name=hostname)
        else:
            addr_id = r["id"]
            logger.info(f"Address {address} already exists with ID {addr_id}, updating name to {hostname}")
            api.update_address(addr_id, name=hostname)
    return r


def add_or_update_zone(
    domain: Annotated[str, typer.Argument(help="Domain name to add the zone to, e.g. example.com")],
):
    with Settings.from_cache().get_api_connection() as api:
        r = api.get_zone(domain)
        if r["count"] == 0:
            logger.info(f"Creating zone for domain {domain}")
            r = api.create_zone(domain)
        else:
            zone_id = r["data"][0]["id"]
            logger.info(f"Zone for domain {domain} already exists with ID {zone_id}")
    return r


@app.command()
def add_or_update_host_record(
    ip: Annotated[str, typer.Argument(help="IP address to add or update")],
    hostname: Annotated[str, typer.Argument(help="Hostname to add or update")],
    domain: Annotated[
        str, typer.Option(help="Domain name to add the host record to, e.g. example.com")
    ] = "netmgmt.utsc.utoronto.ca",
):
    from uoft.core.types import IPAddress

    try:
        address = IPAddress(ip)
    except ValueError as e:
        logger.error(f"Invalid IP address: {ip}. Error: {e}")
        sys.exit(1)
    with Settings.from_cache().get_api_connection() as api:
        addr_id = add_or_update_ip(ip, hostname)["id"]
        zone_id = api.get_zone(domain)["id"]
        try:
            r = api.get_host_record(f"{hostname}.{domain}")
        except ValueError:
            logger.info(f"Creating host record for {address} in domain {domain}")
            r = api.create_host_record(name=hostname, address_id=addr_id, zone_id=zone_id)
        else:
            record_id = r["data"][0]["id"]
            logger.info(f"Host record for {address} already exists with ID {record_id}, updating name to {hostname}")
            api.update_host_record(record_id, dict(addresses=[dict(id=addr_id)]))


@app.command()
def deploy_changes():
    import time

    with Settings.from_cache().get_api_connection() as api:
        servers = api.get_dns_servers()
        servers_by_url = {s[f"/api/v2/servers/{s['id']}"]: s for s in servers}
        failed = False
        with api.threadpool() as pool:
            futures = set()
            for server in servers:
                deployment_roles = server["_embedded"]["deploymentRoles"]
                deployment_roles = set([r["type"] for r in deployment_roles])
                if "DNSDeploymentRole" in deployment_roles:
                    logger.info(f"Scheduling DNS deployment on server {server['name']}")
                    futures.add(pool.submit(api.deploy_changes, server["id"], service="DNS"))
                if "DHCPDeploymentRole" in deployment_roles:
                    logger.info(f"Scheduling DHCP deployment on server {server['name']}")
                    futures.add(pool.submit(api.deploy_changes, server["id"], service="DHCPv4"))

            time.sleep(1)  # give some time for the first tasks to start

            while futures:
                for future in pool.as_completed(futures):
                    result = future.result()
                    futures.remove(future)
                    # logger.debug(f"Deployment result: {result}")
                    deploy_id = result["id"]
                    server_url = result["_links"]["up"]["href"]
                    server = servers_by_url.get(server_url, {"name": "unknown"})
                    state = result["state"]

                    if state in ("PENDING", "QUEUED", "RUNNING"):
                        logger.debug(f"Deployment {deploy_id} is {state}, re-checking later")
                        futures.add(pool.submit(api.deployment_status, deploy_id))
                        time.sleep(0.5)
                        # break here to force `as_completed` to re-evaluate the futures set
                        break

                    elif state == "COMPLETED":
                        logger.success(
                            f"Deployment of {result['service']} on {server['name']} (Deployment {deploy_id}) completed successfully"
                        )
                    elif state == "FAILED":
                        logger.error(
                            f"Deployment of {result['service']} on {server['name']} (Deployment {deploy_id}) failed with message: {result['message']}"
                        )

        if failed:
            logger.error("One or more deployments failed, check log for details")
            sys.exit(1)
        logger.success("All deployments completed")


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


def _debug():
    "Debugging function, only used in active debugging sessions."
    # pylint: disable=all
    # app()
    # add_or_update_host_record("10.14.20.5", "host1", "test.netmgmt.utsc.utoronto.ca")
    deploy_changes()
