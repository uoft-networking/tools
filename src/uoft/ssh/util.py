import importlib
import typing as t
import re

from .pexpect_utils import UofTPexpectSpawn
from uoft.core import logging

from netmiko.cisco_base_connection import CiscoBaseConnection
from netmiko.ssh_autodetect import SSH_MAPPER_BASE, SSH_MAPPER_DICT

if t.TYPE_CHECKING:
    from pexpect import spawn

T = t.TypeVar("T")

logger = logging.getLogger(__name__)



class HostKeyChanged(Exception):
    pass


class UnknownHostKey(Exception):
    pass


class HostKeyAlgorithmMismatch(Exception):
    def __init__(self, theirs: str, *args: object) -> None:
        self.theirs = theirs
        super().__init__(*args)


class KeyExchangeMethodMismatch(HostKeyAlgorithmMismatch):
    pass


class SSHSessionError(Exception):
    """Base class for SSH session errors."""



def register_netmiko_class(cls: T, name: str) -> T:
    """
    Register a netmiko custom class with netmiko's ssh_dispatcher
    """
    # netmiko.ssh_dispatcher is a module, and a function inside netmiko's __init__.py
    # when you import netmiko.ssh_dispatcher, you get the function
    # we need the module
    if t.TYPE_CHECKING:
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



def get_ssh_session(
    host: str,
    username: str,
    password: str,
    command: str | None = None,
    accept_unknown_host=False,
    extra_args: list[str] = [""],
):
    command_line = f"ssh {' '.join(extra_args)} {username}@{host}"
    if command:
        command_line += f" {command}"
    logger.debug(f"Running command: {command_line}")

    child = UofTPexpectSpawn(command_line, encoding="utf-8")
    logger.info("Waiting for password prompt")

    match = child.expect([
        "[pP]assword:",
        "has changed and you have requested strict checking",
        r"no matching (host key type|key exchange method) found. Their offer: (.*)",
        r"The authenticity of host '[^']*' can't be established",
        child.EOF,
    ])
    if match == 1:
        raise HostKeyChanged("Host key has changed")
    elif match == 2:
        logger.error(t.cast(str, child.after).strip())  # type: ignore
        mismatch_type = t.cast(re.Match, child.match).group(1).strip()  # type: ignore
        value = t.cast(re.Match, child.match).group(2).strip()  # type: ignore
        if mismatch_type == "host key type":
            raise HostKeyAlgorithmMismatch(value)
        elif mismatch_type == "key exchange method":
            raise KeyExchangeMethodMismatch(value)
    elif match == 3:
        if accept_unknown_host:
            logger.info(f"Adding host key for {host} to known_hosts")
            child.sendline("yes")
        else:
            raise UnknownHostKey("Host key is unknown")
    elif match == 4:
        raise SSHSessionError(child.before)

    child.sendline(password)
    return child
