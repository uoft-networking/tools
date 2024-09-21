from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.configuration import Config
from nornir.plugins.runners import ThreadedRunner
from nornir.core.plugins.connections import ConnectionPluginRegister
from nornir.core.state import GlobalState
from nornir.core.filter import F # re-exported from nornir.core.filter # noqa: F401
from nornir.core.task import Task, Result # re-exported from nornir.core.task # noqa: F401
from nornir_netmiko.connections.netmiko import Netmiko
from netmiko import BaseConnection
from .nautobot import NautobotInventory

def get_nornir(num_workers=25):
    ConnectionPluginRegister.register("netmiko", Netmiko)
    config = Config()
    config.logging.configure()
    nr = Nornir(
        inventory=NautobotInventory().load(),
        runner=ThreadedRunner(num_workers),
        data=GlobalState(dry_run=False),
        config=config
    )
    return nr

def _debug():
    nr = get_nornir()
    nr = nr.filter(manufacturer="Cisco")

    def test_task(task: Task) -> Result:
        host = task.host
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)
        res = ssh.send_command("show version")
        return Result(host=host, result=res.splitlines()[0])

    print(nr.run(task=test_task))
