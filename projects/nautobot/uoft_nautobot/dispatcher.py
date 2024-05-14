import importlib
from typing import TYPE_CHECKING

from nornir_nautobot.plugins.tasks.dispatcher.default import NetmikoDefault
from netmiko.cisco_base_connection import CiscoBaseConnection


def register_as(name: str):
    def decorator(cls):
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

    return decorator


@register_as("aruba_aoscx")
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


class ArubaNetmikoDispatcher(NetmikoDefault):
    pass
