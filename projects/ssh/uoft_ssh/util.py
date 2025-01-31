import importlib
from typing import TYPE_CHECKING, TypeVar

from netmiko.cisco_base_connection import CiscoBaseConnection
from netmiko.ssh_autodetect import SSH_MAPPER_BASE, SSH_MAPPER_DICT

if TYPE_CHECKING:
    from pexpect import spawn

T = TypeVar("T")



def register_netmiko_class(cls: T, name: str) -> T:
    """
    Register a netmiko custom class with netmiko's ssh_dispatcher
    """
    # netmiko.ssh_dispatcher is a module, and a function
    # when you import netmiko.ssh_dispatcher, you get the function
    # we need the module
    if TYPE_CHECKING:
        import netmiko.ssh_dispatcher as ssh_dispatcher
    else:
        ssh_dispatcher = importlib.import_module("netmiko.ssh_dispatcher")  # type: ignore
    ssh_dispatcher.CLASS_MAPPER_BASE[name] = cls
    ssh_dispatcher.CLASS_MAPPER[name] = cls
    ssh_dispatcher.CLASS_MAPPER[f"{name}_ssh"] = cls
    ssh_dispatcher.platforms = list(ssh_dispatcher.CLASS_MAPPER.keys())
    ssh_dispatcher.platforms.sort()
    ssh_dispatcher.platforms_base = list(ssh_dispatcher.CLASS_MAPPER_BASE.keys())
    ssh_dispatcher.platforms_base.sort()
    ssh_dispatcher.platforms_str = "\n".join(ssh_dispatcher.platforms_base)
    ssh_dispatcher.platforms_str = "\n" + ssh_dispatcher.platforms_str
    return cls


class ArubaOSCXSSH(CiscoBaseConnection):
    # Aruba AOS-CX has no concept of enable mode
    def check_enable_mode(self, *args, **kwargs) -> bool:
        return True

    def enable(self, *args, **kwargs) -> str:
        return ""

    def exit_enable_mode(self, exit_command: str = "disable") -> str:
        return ""

    def disable_paging(
        self,
        command: str = "no page",
        delay_factor: float | None = None,
        cmd_verify: bool = True,
        pattern: str | None = None,
    ) -> str:
        return super().disable_paging(command, delay_factor, cmd_verify, pattern)


def register_aoscx() -> None:
    register_netmiko_class(ArubaOSCXSSH, "aruba_aoscx")
    SSH_MAPPER_DICT["aruba_aoscx"] = dict(
        cmd="show version", pattern=r"ArubaOS-CX", priority=99, dispatch="_autodetect_std"
    )
    SSH_MAPPER_BASE.append(("aruba_aoscx", SSH_MAPPER_DICT["aruba_aoscx"]))
