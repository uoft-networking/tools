from uoft.core import logging
from .base import interface_name_normalize

logger = logging.getLogger(__name__)


def update_switch_intf_configs(switch_hostname: str, *intf_names: str):
    """
    Given a switch hostname and a list of interface names,
    update the interface configurations on the switch
    to match the intended config from Nautobot.
    """
    from .nornir import get_nornir, F, Task, BaseConnection
    from .nautobot import filter_config, get_intended_config

    nr = get_nornir(concurrent=False)
    switch = nr.filter(F(name=switch_hostname))

    switch_config = get_intended_config(switch_hostname)
    switch_config = filter_config(
        config=switch_config,
        filters=[f"^interface {interface_name_normalize(intf)}" for intf in intf_names],
    )
    switch_config = "\n".join(switch_config)

    def update_intf_config(task: Task):
        host = task.host
        logger.info(f"Updating interface configurations for {host.name}...")
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)

        ssh.enable()
        ssh.send_config_set(switch_config, error_pattern=r"%.*", cmd_verify=False)

        ssh.send_command("write memory")
        logger.success(f"Config updated for interfaces: {', '.join(intf_names)} on {host.name}")

    switch.run(update_intf_config, raise_on_error=True)
