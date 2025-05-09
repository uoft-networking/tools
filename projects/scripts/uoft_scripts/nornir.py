from collections import OrderedDict
import json
import typing as t

from uoft_core import logging, txt
from uoft_core.console import console
from uoft_ssh import Settings as SSHSettings

from .nautobot import get_api

from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.plugins.runners import ThreadedRunner, SerialRunner
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.core.state import GlobalState
from nornir.core.filter import F
from nornir.core.task import Task, Result, MultiResult, AggregatedResult
from nornir.core.inventory import Host, Hosts, Inventory, Groups, Defaults, ConnectionOptions
from nornir_netmiko.connections.netmiko import Netmiko
from netmiko import BaseConnection
from netmiko.exceptions import (
    NetmikoTimeoutException, # noqa: F401
    ConfigInvalidException,  # noqa: F401
)  # These are here to be imported by nornir scripts
from rich.pretty import pprint



class NautobotInventory(Inventory):

    @staticmethod
    def _load_gql_data(api):
        query = txt("""
        query {
            devices (platform__isnull: false) {
                id
                hostname: name
                device_type {
                    model
                    manufacturer { name }
                    family: device_family {
                        name
                    }
                }
                software_version { version }
                platform {
                    name
                    network_driver
                }
                primary_ip4 {
                    cidr: address
                    address: host
                }
                primary_ip6 {
                    cidr: address
                    address: host
                }
                status {
                    name
                }
                tags {
                    name
                }
                location {
                    name
                    cf_room_number
                    parent {
                        name
                        cf_building_code
                    }
                }
                role {
                    name
                }
                vlan_group {
                    name
                }
            }
        }
        """)
        return api.graphql.query(query).json["data"]["devices"]

    @classmethod
    def from_nautobot(cls) -> "NautobotInventory":
        """Load of Nornir inventory.

        Returns:
            Inventory: Nornir Inventory
        """
        api = get_api(dev=False)
        hosts = Hosts()

        ssh_s = SSHSettings.from_cache()
        conn_default = ConnectionOptions(extras={"secret": ssh_s.enable_secret.get_secret_value()})
        defaults = Defaults(
            username=ssh_s.personal.username,
            password=ssh_s.personal.password.get_secret_value(),
            connection_options=dict(netmiko=conn_default, napalm=conn_default, paramiko=conn_default),
        )

        for device in cls._load_gql_data(api):  # type: ignore

            name = device["hostname"] or str(device["id"])
            # Add Primary IP address, if found. Otherwise add hostname as the device name
            if device["primary_ip4"]:
                hostname = device["primary_ip4"]["address"]
            elif device["primary_ip6"]:
                hostname = device["primary_ip6"]["address"]
            else:
                hostname: str = device["hostname"]

            # squash nested fields
            device["device_family"] = (
                device["device_type"]["family"]["name"] if device["device_type"]["family"] else None
            )
            device["manufacturer"] = (
                device["device_type"]["manufacturer"]["name"] if device["device_type"]["manufacturer"] else None
            )
            device["device_type"] = device["device_type"]["model"]
            device["network_driver"] = device["platform"]["network_driver"]
            device["platform"] = device["platform"]["name"]
            device["ipv4_cidr"] = device["primary_ip4"]["cidr"] if device["primary_ip4"] else None
            device["ipv4_address"] = device["primary_ip4"]["address"] if device["primary_ip4"] else None
            device["ipv6_cidr"] = device["primary_ip6"]["cidr"] if device["primary_ip6"] else None
            device["ipv6_address"] = device["primary_ip6"]["address"] if device["primary_ip6"] else None
            device["status"] = device["status"]["name"]
            device["tags"] = [tag["name"] for tag in device["tags"]]
            device["room_number"] = (
                device["location"]["cf_room_number"]
                if device["location"] and device["location"]["cf_room_number"]
                else None
            )
            device["building_name"] = (
                device["location"]["parent"]["name"] if device["location"] and device["location"]["parent"] else None
            )
            device["building_code"] = (
                device["location"]["parent"]["cf_building_code"]
                if device["location"]
                and device["location"]["parent"]
                and device["location"]["parent"]["cf_building_code"]
                else None
            )
            device["location"] = device["location"]["name"] if device["location"] else None
            device["role"] = device["role"]["name"] if device["role"] else None
            device["vlan_group"] = device["vlan_group"]["name"] if device["vlan_group"] else None
            device["software_version"] = device["software_version"]["version"] if device["software_version"] else None

            # Add host to hosts by name first, ID otherwise - to string
            host_platform = device["network_driver"]

            host = Host(
                name=name,
                hostname=hostname,
                platform=host_platform,
                data=device,
                # groups=None, # TODO: add support for nautobot dynamic groups
                defaults=defaults,
            )
            hosts[name] = host

        return cls(hosts=hosts, groups=Groups(), defaults=defaults)


def get_nornir(concurrent=True):
    ConnectionPluginRegister.register("netmiko", Netmiko)
    config = Config()
    if concurrent:
        runner = ThreadedRunner(25)
    else:
        runner = SerialRunner()
    state = GlobalState(dry_run=False)
    nr = Nornir(inventory=NautobotInventory.from_nautobot(), runner=runner, data=state, config=config)
    return nr


def sample_by(nr: Nornir, field: str):
    """
    Return a new Nornir instance with one host from each unique value of the given field

    Example:
        nr = get_nornir()
        nr_sample = sample_by(nr, "role")
        # nr_sample.inventory.hosts will contain one host for each unique role
    """
    hosts = nr.inventory.hosts
    unique_values = set([host.get(field) for host in hosts.values()])
    filtered_hosts: Hosts = {}  # pyright: ignore[reportAssignmentType]
    for value in unique_values:
        name, host = nr.filter(F(**{field: value})).inventory.hosts.popitem()
        filtered_hosts[name] = host
    new_inventory = Inventory(hosts=filtered_hosts)
    nr_sample = Nornir(inventory=new_inventory, runner=nr.runner, data=nr.data, config=nr.config)
    return nr_sample


def _get_color(result: Result, failed: bool) -> str:
    if result.failed or failed:
        color = "red"
    elif result.changed:
        color = "yellow"
    else:
        color = "green"
    return color


def _print_individual_result(
    result: Result,
    attrs: list[str],
    failed: bool,
    severity_level: int,
    task_group: bool = False,
    print_host: bool = False,
) -> None:
    if result.severity_level < severity_level:
        return
    con = console()

    color = _get_color(result, failed)
    subtitle = "" if result.changed is None else " ** changed : {} ".format(result.changed)
    symbol = "v" if task_group else "-"
    host = f"{result.host.name}: " if (print_host and result.host and result.host.name) else ""
    msg = "{} {}{}{}".format(symbol * 4, host, result.name, subtitle)
    if task_group:
        con.print(f"[bold {color}]{msg:v<80}[/]")
    else:
        con.print(f"[bold {color}]{msg:-<80}[/]")
    for attribute in attrs:
        x = getattr(result, attribute, "")
        if isinstance(x, BaseException):
            # for consistency between py3.6 and py3.7
            con.print(f"{x.__class__.__name__}{x.args}")
        elif x and not isinstance(x, str):
            if isinstance(x, OrderedDict):
                con.print_json(json.dumps(x, indent=2))
            else:
                pprint(x, console=con)
        elif x:
            con.print(x)


def print_result(
    result: AggregatedResult | Result | MultiResult,
    attrs: list[str] | None = None,
    failed: bool = False,
    severity_level: int = logging.INFO,
    print_host: bool = False,
) -> None:
    con = console()
    attrs = attrs or ["diff", "result", "stdout"]
    if isinstance(attrs, str):
        attrs = [attrs]

    if isinstance(result, AggregatedResult):
        msg = result.name
        msg += " "
        con.print(f"[bold cyan]{msg:*<80}[/]")
        for host, host_data in sorted(result.items()):
            title = "" if host_data.changed is None else " ** changed : {} ".format(host_data.changed)
            msg = "* {}{} ".format(host, title)
            con.print(f"[bold blue]{msg:*<80}[/]")
            print_result(host_data, attrs, failed, severity_level)
    elif isinstance(result, MultiResult):
        _print_individual_result(
            result[0],
            attrs,
            failed,
            severity_level,
            task_group=True,
            print_host=print_host,
        )
        for r in result[1:]:
            print_result(r, attrs, failed, severity_level)
        color = _get_color(result[0], failed)
        msg = "^^^^ END {} ".format(result[0].name)
        if result[0].severity_level >= severity_level:
            con.print(f"[bold {color}]{msg:^<80}[/]")
    elif isinstance(result, Result):
        _print_individual_result(result, attrs, failed, severity_level, print_host=print_host)


def _debug():
    nr = get_nornir()
    target = nr.filter(status="Active")

    def test_task(task: Task) -> Result:
        host: Host = task.host
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)
        ssh.enable()
        version_info = t.cast(str, ssh.send_command("show version"))
        result = version_info.splitlines()[0]
        return Result(host=host, result=result)

    res: AggregatedResult = target.run(task=test_task)
    print_result(res)  # type: ignore
