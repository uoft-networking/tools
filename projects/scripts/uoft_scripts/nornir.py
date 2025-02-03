from collections import OrderedDict
import json

from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.plugins.runners import ThreadedRunner, SerialRunner
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.core.state import GlobalState
from nornir.core.filter import F
from nornir.core.task import Task, Result, MultiResult, AggregatedResult
from nornir.core.inventory import Host
from nornir_netmiko.connections.netmiko import Netmiko
from netmiko import BaseConnection
from rich.console import Console
from rich.pretty import pprint
from .nautobot import NautobotInventory
from uoft_core import logging


def get_nornir(concurrent=True):
    ConnectionPluginRegister.register("netmiko", Netmiko)
    config = Config()
    if concurrent:
        runner = ThreadedRunner(25)
    else:
        runner = SerialRunner()
    state = GlobalState(dry_run=False)
    nr = Nornir(inventory=NautobotInventory().load(), runner=runner, data=state, config=config)
    return nr


_CONSOLE = None


def _get_console():
    global _CONSOLE
    if _CONSOLE is None:
        _CONSOLE = Console()
    return _CONSOLE


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
    con = _get_console()

    color = _get_color(result, failed)
    subtitle = "" if result.changed is None else " ** changed : {} ".format(result.changed)
    level_name = logging.getLevelName(result.severity_level)
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
    con = _get_console()
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
    target = nr.filter(status="Active", role__in=["Core Switches", "Distribution Switches", "Data Centre Switches"])

    def test_task(task: Task) -> Result:
        host: Host = task.host
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)
        version_info = ssh.send_command("show version")
        result = version_info.splitlines()[0]  # type: ignore
        return Result(host=host, result=result)

    res: AggregatedResult = target.run(task=test_task)
    print_result(res)  # type: ignore
