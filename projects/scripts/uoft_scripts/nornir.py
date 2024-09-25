from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.plugins.runners import ThreadedRunner, SerialRunner
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.core.state import GlobalState
from nornir.core.filter import F
from nornir.core.task import Task, Result, AggregatedResult
from nornir.core.inventory import Host
from nornir_utils.plugins.functions import print_result
from nornir_netmiko.connections.netmiko import Netmiko
from netmiko import BaseConnection
from .nautobot import NautobotInventory

def get_nornir(concurrent=True):
    ConnectionPluginRegister.register("netmiko", Netmiko)
    config = Config()
    if concurrent:
        runner = ThreadedRunner(25)
    else:
        runner = SerialRunner()
    state = GlobalState(dry_run=False)
    nr = Nornir(
        inventory=NautobotInventory().load(),
        runner=runner,
        data=state,
        config=config
    )
    return nr

def _debug():
    nr = get_nornir()
    target = nr.filter(F(role="Core Switches") | F(role="Distribution Switches") | F(role="Data Centre Switches"))
    h: Host = next(iter(nr.inventory.hosts.values()))
    assert h.name
    assert h.hostname
    assert h.platform
    assert h.data

    def test_task(task: Task) -> Result:
        host = task.host
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)
        version_info = ssh.send_command("show version")
        result = version_info.splitlines()[0] # type: ignore
        return Result(host=host, result=result)

    res: AggregatedResult = target.run(task=test_task)
    print_result(res) # type: ignore
