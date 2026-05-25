from importlib.metadata import version

from uoft_core import logging

# All of our projects are distributed as packages, so we can use the importlib.metadata 
# module to get the version of the package.
assert __package__
__version__ = version(__package__) # type: ignore

logger = logging.getLogger(__name__)


def interface_name_normalize(intf_name: str) -> str:
    """
    Normalizes network interface names to their full canonical forms.

    This function converts common shorthand interface names (e.g., "Et99", "Te1/0/1")
    to their full names (e.g., "Ethernet99", "TenGigabitEthernet1/0/1") for consistency,
    such as when performing lookups in systems like Nautobot. The normalization is
    idempotent and avoids transforming already normalized names (e.g., "Ethernet99"
    remains unchanged).

    Supported shorthand expansions:
        - "Et" → "Ethernet"
        - "Fo" → "FortyGigabitEthernet"
        - "Te" → "TenGigabitEthernet"
        - "Gi" → "GigabitEthernet"
        - "Fa" → "FastEthernet"
        - "Po" → "Port-Channel"
        - "Lo" → "Loopback"
        - "Ma" → "Management"

    Args:
        intf_name (str): The interface name to normalize.

    Returns:
        str: The normalized, full interface name.
    """
    # This would be so much simpler to implement with a regex,
    # but i think there'd be a heavier performance cost
    match intf_name[:2]:
        case "Et" if not intf_name[:3] == "Eth":
            return intf_name.replace("Et", "Ethernet", 1)
        case "Fo" if not intf_name[:3] == "For":
            return intf_name.replace("Fo", "FortyGigabitEthernet", 1)
        case "Te" if not intf_name[:3] == "Ten":
            return intf_name.replace("Te", "TenGigabitEthernet", 1)
        case "Gi" if not intf_name[:3] == "Gig":
            return intf_name.replace("Gi", "GigabitEthernet", 1)
        case "Fa" if not intf_name[:3] == "Fas":
            return intf_name.replace("Fa", "FastEthernet", 1)
        case "Po" if not intf_name[:3] == "Por":
            return intf_name.replace("Po", "Port-Channel", 1)
        case "Lo" if not intf_name[:3] == "Loo":
            return intf_name.replace("Lo", "Loopback", 1)
        case "Ma" if not intf_name[:3] == "Man":
            return intf_name.replace("Ma", "Management", 1)
        case _:
            # If the interface name is already in its full form, return it as is
            # This is idempotent, so calling this function on an already normalized name will not change it
            return intf_name


def interface_name_denormalize(intf_name: str) -> str:
    """
    Converts a full-form network interface name to its shorthand notation.

    This function takes a network interface name in its expanded form (e.g., "Ethernet99", "TenGigabitEthernet1/0/1")
    and returns the corresponding abbreviated version (e.g., "Et99", "Te1/0/1"). It supports common interface types
    such as Ethernet, TenGigabitEthernet, GigabitEthernet, FastEthernet, Port-Channel, Loopback, and Management.

    Args:
        intf_name (str): The full-form interface name to be converted.

    Returns:
        str: The shorthand version of the interface name.
    """
    # Switches oft times report their intf names in shorthand:
    # Ethernet99 instead of Et99, TenGigabitEthernet1/0/1 instead of Te1/0/1
    # We need to denormalize this to the shorthand name
    if intf_name.startswith("Ethernet"):
        intf_name = intf_name.replace("Ethernet", "Et")
    elif intf_name.startswith("TenGigabitEthernet"):
        intf_name = intf_name.replace("TenGigabitEthernet", "Te")
    elif intf_name.startswith("GigabitEthernet"):
        intf_name = intf_name.replace("GigabitEthernet", "Gi")
    elif intf_name.startswith("FastEthernet"):
        intf_name = intf_name.replace("FastEthernet", "Fa")
    elif intf_name.startswith("Port-Channel"):
        intf_name = intf_name.replace("Port-Channel", "Po")
    elif intf_name.startswith("Loopback"):
        intf_name = intf_name.replace("Loopback", "Lo")
    elif intf_name.startswith("Management"):
        intf_name = intf_name.replace("Management", "Ma")
    return intf_name

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


