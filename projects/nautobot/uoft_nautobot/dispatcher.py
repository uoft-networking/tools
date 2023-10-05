from typing import Optional
from nornir_nautobot.plugins.tasks.dispatcher.default import NetmikoNautobotNornirDriver
from netmiko.ssh_dispatcher import register_as
from netmiko.cisco_base_connection import CiscoBaseConnection

@register_as("aruba_aoscx")
class ArubaOSCXSSH(CiscoBaseConnection):
    # Aruba AOS-CX has no concept of enable mode
    def check_enable_mode(self, *args, **kwargs) -> bool:
        return True

    def enable(self, *args, **kwargs) -> str:
        return ""

    def exit_enable_mode(self, exit_command: str = "disable") -> str:
        return ""
    
    def disable_paging(self, command: str = "no page", delay_factor: float | None = None, cmd_verify: bool = True, pattern: str | None = None) -> str:
        return super().disable_paging(command, delay_factor, cmd_verify, pattern)


class ArubaNetmikoDispatcher(NetmikoNautobotNornirDriver):
    pass
