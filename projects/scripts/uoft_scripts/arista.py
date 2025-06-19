from dataclasses import dataclass
from functools import cached_property
from time import sleep
import typing as t

from pexpect import TIMEOUT
from uoft_core.console import console
from uoft_ssh.cli import get_ssh_session
from uoft_ssh import Settings as SSHSettings
from uoft_core import logging
from uoft_core import BaseSettings, SecretStr

from . import interface_name_normalize, interface_name_denormalize


if t.TYPE_CHECKING:
    from uoft_ssh.pexpect_utils import UofTPexpectSpawn
    from pynautobot.models.dcim import Devices, Interfaces
    from pynautobot.models.extras import Record


class Settings(BaseSettings):
    cvp_token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "arista"


logger = logging.getLogger(__name__)


def _get_ssh_session(
    terminal_server: str,
    port: int,
):
    creds = SSHSettings.from_cache().terminal_server
    username = f"{creds.username}:port{port}"

    ssh = get_ssh_session(
        host=terminal_server,
        username=username,
        password=creds.password.get_secret_value(),
    )

    return ssh


def get_onboarding_token():
    "Generate a CVP onboarding token"
    import grpc
    from grpc_reflection.v1alpha.proto_reflection_descriptor_database import ProtoReflectionDescriptorDatabase
    from google.protobuf.descriptor_pool import DescriptorPool
    from google.protobuf.message_factory import GetMessageClass

    s = Settings.from_cache()

    credentials = grpc.composite_channel_credentials(
        grpc.ssl_channel_credentials(),
        grpc.access_token_call_credentials(s.cvp_token.get_secret_value()),
    )
    # Create a gRPC channel
    channel = grpc.secure_channel(target="www.cv-prod-na-northeast1-b.arista.io:443", credentials=credentials)

    # gather needed metadata from the gRPC reflection service
    reflection_db = ProtoReflectionDescriptorDatabase(channel)
    desc_pool = DescriptorPool(reflection_db)
    token_request = GetMessageClass(desc_pool.FindMessageTypeByName("admin.AddEnrollmentTokenRequest"))
    token_response = GetMessageClass(desc_pool.FindMessageTypeByName("admin.AddEnrollmentTokenResponse"))

    # Create a bound method for the gRPC call
    method = channel.unary_unary(
        "/admin.Enrollment/AddEnrollmentToken",
        request_serializer=token_request().SerializeToString,  # pyright: ignore[reportArgumentType]
        response_deserializer=token_response.FromString,
    )

    # Call the method
    res = method(request=token_request)

    return res.enrollmentToken.token


def _put_switch_in_config_mode(ssh: "UofTPexpectSpawn"):
    """
    Given an open pexpect session to a port on a terminal server,
    take the switch attached to that port from whatever state it's currently in
    and put it into config mode
    """

    ssh.multi_expect(timeout=5)

    @ssh.multi_expect.register(ssh.TIMEOUT)
    def _():
        logger.info("Terminal server not yet ready, going to poke it and wait some more...")
        ssh.sendline("")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Press RETURN to get started.")
    def _():
        logger.info("Switch is now available and responding.")
        ssh.sendline("")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Would you like to enter the initial configuration dialog?")
    def _():
        logger.info("This switch is uninitialized, and has booted into the config wizard. Cancelling the wizard...")
        ssh.sendline("no")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Switch>")
    def _():
        logger.info("This switch is uninitialized. Entering enable mode now...")
        ssh.sendline("enable")
        sleep(1)
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Zero Touch Provisioning mode")
    def _():
        logger.info("This switch is uninitialized and in ZTP mode. Logging in and disabling ZTP...")
        ssh.expect(r"localhost login:")
        ssh.sendline("admin")
        ssh.expect(r"localhost>")
        ssh.sendline("zerotouch disable")
        logger.info("ZTP disabled, rebooting switch...")
        ssh.expect(r"Restarting system")
        sleep(120)
        # When switch reboots, it sometimes prints undecodable bytes to the terminal, like `\xff\x00`
        # This causes the expect loop to fail, so we need to set codec_errors to "replace" to ignore them
        # temporarily
        decoder = ssh._decoder  # pyright: ignore[reportAttributeAccessIssue]
        decoder.errors = "replace"
        ssh.expect("Aboot")  # Once we see this, we know the switch is booting back up and can replace the codec_errors
        decoder.errors = ssh.codec_errors
        logger.debug("Switch is now booting up, waiting for it to be ready...")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"localhost login:")
    def _():
        logger.info("This switch is uninitialized. Logging in now...")
        ssh.sendline("admin")
        sleep(1)
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"([a-zA-Z0-9-]+) login:")
    def _():
        # First try logging in as yourself, assuming this is a fully initialized switch
        username = SSHSettings.from_cache().personal.username
        ssh.sendline(username)
        ssh.expect(r"Password:", timeout=1)
        ssh.sendline(SSHSettings.from_cache().personal.password.get_secret_value())
        try:
            ssh.expect("incorrect", timeout=1)
        except ssh.TIMEOUT:
            # If we didn't get an "incorrect" message, we are logged in
            logger.info(f"Logged in successfully as {username}")
            return ssh.multi_expect.reenter_loop()
        logger.info("This appears to be a partially initialized switch. Logging in as admin now...")
        ssh.sendline("admin")
        sleep(1)
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"localhost#")
    def _():
        logger.info("This (Arista?) switch is uninitialized and in enable mode. Entering config mode now...")
        ssh.sendline("terminal length 0")
        ssh.sendline("configure terminal")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"([a-zA-Z0-9-]+)#")
    def _():
        logger.info("This switch is now in enable mode.")
        ssh.sendline("terminal length 0")
        ssh.sendline("configure terminal")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"([a-zA-Z0-9-]+)>")
    def _():
        logger.info("We are now logged into a partially initialized switch. Entering 'enable' mode...")
        ssh.sendline("enable")
        # at this point, the switch may or may not be configured to require an enable password
        # if it is, we will get a password prompt
        res = ssh.expect([r"Password:", r"([a-zA-Z0-9-]+)#"])
        if res == 0:
            # we got a password prompt, so we need to enter the password
            logger.info("This switch requires a password to enter enable mode, entering it now...")
            ssh.sendline(SSHSettings.from_cache().enable_secret.get_secret_value())
        else:
            # we are already in enable mode, poke the switch to trigger a new line before reentering expect loop
            ssh.sendline("")
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Username:")
    def _():
        logger.info("This switch has been at least partially initialized. Logging in now...")
        ssh.sendline(SSHSettings.from_cache().personal.username)
        sleep(1)
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"Password:")
    def _():
        logger.info("Entering switch password...")
        ssh.sendline(SSHSettings.from_cache().personal.password.get_secret_value())
        return ssh.multi_expect.reenter_loop()

    @ssh.multi_expect.register(r"([a-zA-Z0-9-]+)\(config\)#")
    def _():
        logger.info("This switch is now in config mode.")
        return

    @ssh.multi_expect.register(r"([a-zA-Z0-9-]+)\(([a-zA-Z0-9-]+)\)#")
    def _():
        logger.info("This switch is in some unknown config mode, dropping back down to enable mode...")
        ssh.sendcontrol("c")
        return ssh.multi_expect.reenter_loop()

    return ssh.multi_expect.start()


def _wait_for_switch_to_come_online(ip: str):
    """
    Wait for a switch to come online by poking it on port 22
    until it responds or times out.
    """
    import socket

    logger.info(f"Waiting for {ip} to come online...")
    while True:
        try:
            socket.create_connection((ip, 22), timeout=5)
            break
        except socket.timeout:
            logger.info(f"{ip} is not yet online, waiting 5 seconds...")
            sleep(5)
    logger.success(f"{ip} is now online!")



def initial_provision(switch_hostname: "str | Devices", terminal_server: str, port: int):
    """
    Given a switch hostname, terminal server, and port,
    connect to the switch via the terminal server
    and give it the minimum viable config necessary
    to get it online and accessible via SSH over OOB
    (including RADIUS auth)
    """
    from .nautobot import get_api, get_minimum_viable_config
    from rich.progress import track

    nb = get_api(dev=False)
    if isinstance(switch_hostname, str):
        switch = nb.dcim.devices.get(name=switch_hostname)
    else:
        switch = switch_hostname
    switch = t.cast("Devices", switch)
    if not switch:
        logger.error(f"Switch {switch_hostname} not found in Nautobot")
        return

    mgmt_intf = nb.dcim.interfaces.get(device=switch.id, name="Management1")
    if not mgmt_intf:
        logger.error(f"Switch {switch_hostname} does not have a Management1 interface")
        return
    mgmt_intf = t.cast("Record", mgmt_intf)
    if not mgmt_intf.enabled:
        logger.info(f"Enabling Management1 interface on {switch_hostname}")
        mgmt_intf.update(dict(enabled=True))

    # intf role
    if mgmt_intf.role is None or mgmt_intf.role.name == "Management":
        logger.info(f"Setting Management1 interface role to Management on {switch_hostname}")
        role = nb.extras.roles.get(name="Management")
        mgmt_intf.update(dict(role=role))

    if len(mgmt_intf.ip_addresses) == 0:  # pyright: ignore[reportArgumentType]
        logger.warning(f"Switch {switch_hostname} does not have an OOB IP address assigned")
        oob_pfx = nb.ipam.prefixes.get(prefix="192.168.64.0/22")
        logger.warning(f"Assigning next available IP to {switch_hostname}")
        oob_ip = oob_pfx.available_ips.create(  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
            data=dict(status="Active", dns_name=f"{switch_hostname}-oob", description=f"{switch_hostname}-oob")
        )
        nb.ipam.ip_address_to_interface.create(dict(ip_address=oob_ip.id, interface=mgmt_intf.id))  # type: ignore
        switch.update(dict(primary_ip4=oob_ip.id))  # type: ignore
        logger.info(f"Assigned IP {oob_ip.address} to {switch_hostname}")
    else:
        oob_ip = t.cast(list["Record"], mgmt_intf.ip_addresses)[0]  # type: ignore

    ssh = _get_ssh_session(terminal_server, port)

    _put_switch_in_config_mode(ssh)

    logger.info("Switch is now in config mode, ready to accept configuration commands.")

    # At this point, we want to deploy only the minimum viable config to the switch necessary to get it
    # online and accessible via SSH (including RADIUS auth)

    # The rest of the config can then be deployed via Nornir/SSH, much faster and more reliable than
    # trying to do it all in one go here

    # rather than try to replicate and recreate the minimum viable bits of config here, (including RADIUS keys, etc)
    # we will get the full intended config from nautobot, and filter it down to just the lines we want / care about
    minimum_config = get_minimum_viable_config(switch_hostname)

    for line in track(minimum_config, description="Pushing config to switch...", console=console()):
        logger.debug(f"Sending command: {line}")
        ssh.sendline(line)
        res = ssh.expect([r"%.*", TIMEOUT], timeout=0.5)
        if res == 0:
            logger.error(f"Command {line} failed with error: {ssh.after}")
            raise RuntimeError(f"Command {line} failed with error: {ssh.after}")

    logger.success(
        "Switch is now ready for onboarding. It can be accessed via SSH with the admin "
        f"account at IP address {oob_ip.address} and should show up in CVP momentarily"
    )
    ssh.sendline("wr mem")


def wipe_switch(terminal_server: str, port: int, reenable_ztp_mode: bool = False):
    """
    Given a terminal server and port,
    wipe the Arista switch attached to that port
    and reset it to factory defaults.
    This is used for testing and debugging.
    """
    ssh = _get_ssh_session(terminal_server, port)
    _put_switch_in_config_mode(ssh)
    ssh.sendline("bash")
    logger.info("erasing flash...")
    ssh.sendline("rm /mnt/flash/startup-config")  # This one might fail, but that's ok
    if reenable_ztp_mode:
        ssh.sendline("rm /mnt/flash/zerotouch-config")
    ssh.sendline("logout")
    logger.info("Rebooting switch...")
    ssh.sendline("reload")
    ssh.expect("Save?")
    ssh.sendline("no")
    ssh.expect("Proceed with reload?")
    ssh.sendline("")
    ssh.expect("Restarting system")
    logger.success("Switch has been wiped and is now rebooting")
    return



@dataclass(eq=False, kw_only=True)
class DeviceRecord:
    name: str

    @cached_property
    def nb(self) -> "Devices":
        from .nautobot import get_api

        api = get_api(dev=False)
        return api.dcim.devices.get(name=self.name)  # pyright: ignore[reportReturnType]


@dataclass(eq=False, kw_only=True)
class InterfaceRecord:
    device: DeviceRecord
    name: str

    @cached_property
    def nb(self) -> "Interfaces":
        from .nautobot import get_api

        api = get_api(dev=False)
        return api.dcim.interfaces.get(device=self.device.nb.id, name=self.name)  # pyright: ignore[reportReturnType, reportAttributeAccessIssue]


@dataclass(eq=False, kw_only=True)
class Link:
    local: InterfaceRecord
    remote: InterfaceRecord

    def reverse(self) -> "Link":
        return Link(local=self.remote, remote=self.local)


@dataclass(eq=False, kw_only=True)
class Dist(DeviceRecord):
    link_to_spine1: Link | None = None
    link_to_spine2: Link | None = None
    lag_to_spines: InterfaceRecord | None = None

    @cached_property
    def vl666_id(self) -> str:
        from .nautobot import get_api

        api = get_api(dev=False)
        vl666 = api.ipam.vlans.get(vlan_group=self.nb.vlan_group.id, vid=666)  # pyright: ignore[reportOptionalMemberAccess]
        if not vl666:
            logger.error("VLAN 666 not found in Nautobot")
            raise ValueError("VLAN 666 not found in Nautobot")
        return t.cast(str, vl666.id)  # pyright: ignore[reportAttributeAccessIssue]


@dataclass(eq=False, kw_only=True)
class Spine(DeviceRecord):
    link_to_dist: Link | None = None
    lag_to_dist: Link | None = None
    mlag_peers: list[Link]
    link_to_leafs: list[Link]


@dataclass(eq=False, kw_only=True)
class Leaf(DeviceRecord):
    link_to_spine1: Link | None = None
    link_to_spine2: Link | None = None


@dataclass(eq=False, kw_only=True)
class LLDPData:
    dist: Dist
    spine1: Spine
    spine2: Spine
    leafs: list[Leaf]


def _parse_lldp_data(
    lldp_data: dict[str, list[dict[str, str]]],
    dist_switch_hostname: str,
    arista_switch_names: tuple[str, ...],
) -> LLDPData:
    from .nautobot import get_api

    api = get_api(dev=False)
    dist = Dist(name=dist_switch_hostname)
    spine1 = Spine(name=arista_switch_names[0], mlag_peers=[], link_to_leafs=[])
    spine2 = Spine(name=arista_switch_names[1], mlag_peers=[], link_to_leafs=[])
    leafs = [Leaf(name=leaf_hostname) for leaf_hostname in arista_switch_names[2:]]

    def _get_or_create_dist_lag(spine_name: str):
        # find the next free port channel number on the dist switch
        # TODO: right now this is cisco-specific, needs to be able to handle arista dist switches too

        label_fragment = spine_name.partition("-")[2]
        # given a spine name like `a1-ev0c-arista`, this will give us `ev0c-arista`

        lags = api.dcim.interfaces.filter(device=dist.nb.id, type="lag")
        if lags and (existing_lag := next((lag for lag in lags if label_fragment in lag.label), None)):  # pyright: ignore[reportAttributeAccessIssue, reportOperatorIssue]
            lag_name = t.cast(str, existing_lag.name)  # pyright: ignore[reportAttributeAccessIssue]
            logger.info(f"Found existing port channel {lag_name} on {dist.name}")
            existing_lag = t.cast("Interfaces", existing_lag)
            return InterfaceRecord(device=dist, name=lag_name)

        lag_numbers = sorted([int(lag.name.partition("hannel")[2]) for lag in lags])  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
        next_lag_number = lag_numbers[-1] + 1 if lag_numbers else 1
        lag_name = f"Port-Channel{next_lag_number}"
        logger.info(f"Creating new port channel {next_lag_number} on {dist_switch_hostname} for {label_fragment}")
        api.dcim.interfaces.create(
            dict(
                name=lag_name,
                label=f"{label_fragment}-Po1",
                type="lag",
                status="Active",
                device=dist.nb.id,
                mode="tagged-all",
                untagged_vlan=dist.vl666_id,
            )
        )
        return InterfaceRecord(device=dist, name=lag_name)

    # Map out the trunk links from dist to spines
    dist.lag_to_spines = _get_or_create_dist_lag("spine")
    spine_uplink_lag_name = "Port-Channel1"
    for link_dict in lldp_data[dist.name]:
        if link_dict["neighbor_name"] == spine1.name:
            local_intf = interface_name_normalize(link_dict["local_interface"])
            remote_intf = interface_name_normalize(link_dict["neighbor_interface"])
            dist.link_to_spine1 = Link(
                local=InterfaceRecord(device=dist, name=local_intf),
                remote=InterfaceRecord(device=spine1, name=remote_intf),
            )
            spine1.link_to_dist = dist.link_to_spine1.reverse()
            spine1.lag_to_dist = Link(
                remote=dist.lag_to_spines, local=InterfaceRecord(device=spine1, name=spine_uplink_lag_name)
            )
        elif link_dict["neighbor_name"] == spine2.name:
            local_intf = interface_name_normalize(link_dict["local_interface"])
            remote_intf = interface_name_normalize(link_dict["neighbor_interface"])
            dist.link_to_spine2 = Link(
                local=InterfaceRecord(device=dist, name=local_intf),
                remote=InterfaceRecord(device=spine2, name=remote_intf),
            )
            spine2.link_to_dist = dist.link_to_spine2.reverse()
            spine2.lag_to_dist = Link(
                remote=dist.lag_to_spines, local=InterfaceRecord(device=spine2, name=spine_uplink_lag_name)
            )

    # Map out the mlag peer links between spines
    for link_dict in lldp_data[spine1.name]:
        if link_dict["neighbor_name"] != spine2.name:
            continue
        local_intf = interface_name_normalize(link_dict["local_interface"])
        remote_intf = interface_name_normalize(link_dict["neighbor_interface"])
        link = Link(
            local=InterfaceRecord(device=spine1, name=local_intf),
            remote=InterfaceRecord(device=spine2, name=remote_intf),
        )
        spine1.mlag_peers.append(link)
        spine2.mlag_peers.append(link.reverse())

    # Map out the leaf links to spines
    for leaf in leafs:
        for link_dict in lldp_data[leaf.name]:
            if link_dict["neighbor_name"] == spine1.name:
                local_intf = interface_name_normalize(link_dict["local_interface"])
                remote_intf = interface_name_normalize(link_dict["neighbor_interface"])
                link = Link(
                    local=InterfaceRecord(device=leaf, name=local_intf),
                    remote=InterfaceRecord(device=spine1, name=remote_intf),
                )
                leaf.link_to_spine1 = link
                spine1.link_to_leafs.append(link.reverse())
            elif link_dict["neighbor_name"] == spine2.name:
                local_intf = interface_name_normalize(link_dict["local_interface"])
                remote_intf = interface_name_normalize(link_dict["neighbor_interface"])
                link = Link(
                    local=InterfaceRecord(device=leaf, name=local_intf),
                    remote=InterfaceRecord(device=spine2, name=remote_intf),
                )
                leaf.link_to_spine2 = link
                spine2.link_to_leafs.append(link.reverse())

    return LLDPData(dist=dist, spine1=spine1, spine2=spine2, leafs=leafs)


def map_stack_connections(dist_switch_hostname: str, *arista_switch_names: str):
    """
    Given a dist switch and a list of arista switches to organize into an mlag leaf-spine stack,
    login to each over ssh, identify connections between them all using LLDP, identify port roles
    for each port of each connection, and push the data to nautobot
    """
    from .nornir import get_nornir, F, Task, BaseConnection
    from .nautobot import get_api

    nr = get_nornir()

    nr = nr.filter(F(name__in=[dist_switch_hostname, *arista_switch_names]))

    lldp_data_raw = dict()

    def get_lldp_data(task: Task):
        host = task.host
        ssh: BaseConnection = task.host.get_connection("netmiko", task.nornir.config)
        res = ssh.send_command("show lldp neighbors", use_textfsm=True)
        lldp_data_raw[host.name] = res

    nr.run(get_lldp_data)

    # import pickle
    # pickle.dump(lldp_data_raw, open('.uoft_core.debug.arista_lldp.pkl', 'wb'))
    # lldp_data_raw = pickle.load(open(".uoft_core.debug.arista_lldp.pkl", "rb"))

    lldp_data = _parse_lldp_data(lldp_data_raw, dist_switch_hostname, arista_switch_names)

    assert lldp_data.dist.link_to_spine1 is not None
    assert lldp_data.dist.link_to_spine2 is not None
    assert lldp_data.dist.lag_to_spines is not None
    assert lldp_data.spine1.link_to_dist is not None
    assert lldp_data.spine2.link_to_dist is not None
    assert lldp_data.spine1.lag_to_dist is not None
    assert lldp_data.spine2.lag_to_dist is not None
    assert lldp_data.spine1.mlag_peers is not None
    assert lldp_data.spine2.mlag_peers is not None
    assert lldp_data.spine1.link_to_leafs is not None
    assert lldp_data.spine2.link_to_leafs is not None
    assert lldp_data.leafs is not None

    api = get_api(dev=False)

    # create vl4094 interface on spine switches
    for spine in (lldp_data.spine1, lldp_data.spine2):
        vl4094_intf = api.dcim.interfaces.get(device=spine.nb.id, name="Vlan4094")
        if not vl4094_intf:
            logger.info(f"Creating Vlan4094 interface on {spine.name}")
            api.dcim.interfaces.create(
                device=spine.nb.id,
                name="Vlan4094",
                type="virtual",
                status="Active",
                enabled=True,
                role="Stack Link",
            )
        else:
            logger.info(f"Found existing Vlan4094 interface on {spine.name}")
            vl4094_intf.update(  # pyright: ignore[reportAttributeAccessIssue]
                dict(
                    status="Active",
                    enabled=True,
                    role="Stack Link",
                )
            )

    def _get_or_create_intfs(link: Link, peer_link: bool = False, lag: Link | None = None):
        # if peer_link is False, we are creating/updating an 'Uplink' interface on the local side
        # and a 'Downlink' intf on the remote side
        # if peer_link is True, we are creating/updating a 'Stack Link' intf on both sides
        logger.debug(
            f"Creating/updating interfaces for link between "
            f"{link.local.device.name}-{interface_name_denormalize(link.local.name)} and "
            f"{link.remote.device.name}-{interface_name_denormalize(link.remote.name)}"
        )

        # if lag is None, we are creating/updating a lag interface
        # if lag is not None, we are creating/updating a lag member interface tied to a lag
        local_role = "Stack Link" if peer_link else "Uplink"
        remote_role = "Stack Link" if peer_link else "Downlink"

        # get or create the lag on the local device
        local_intf_data = dict(
            label=f"{link.remote.device.name}-{interface_name_denormalize(link.remote.name)}",
            status="Active",
            role=local_role,
            mode="tagged-all",
            untagged_vlan=lldp_data.dist.vl666_id,
        )
        if lag:
            local_intf_data["lag"] = lag.local.nb.id  # pyright: ignore[reportArgumentType]

        local_intf = api.dcim.interfaces.get(device=link.local.device.nb.id, name=link.local.name)
        if not local_intf:
            if lag:
                # this is a member interface, which means it's a physical interface,
                # which means it should already exist in nautobot, as part of the device type
                # if this interface doesn't already exist in nautobot, something has gone very wrong
                raise ValueError(
                    f"Interface {link.local.name} on {link.local.device.name}, identified as being "
                    f"connected to {link.remote.name} on {link.remote.device.name} does not exist in Nautobot."
                    f"Are you sure {link.local.device.name} has been properly set up?"
                )
            logger.info(f"Creating interface {link.local.name} on {link.local.device.name}")
            local_intf = api.dcim.interfaces.create(
                device=link.local.device.nb.id, name=link.local.name, type="lag", **local_intf_data
            )
        else:
            logger.info(f"Updating existing interface {link.local.name} on {link.local.device.name}")
            local_intf = t.cast("Interfaces", local_intf)
            local_intf.update(local_intf_data)

        # get or create the lag on the remote device
        remote_intf_data = dict(
            label=f"{link.local.device.name}-{interface_name_denormalize(link.local.name)}",
            status="Active",
            role=remote_role,
            mode="tagged-all",
            untagged_vlan=lldp_data.dist.vl666_id,
        )
        if lag:
            remote_intf_data["lag"] = lag.remote.nb.id  # pyright: ignore[reportArgumentType]
        remote_intf = api.dcim.interfaces.get(device=link.remote.device.nb.id, name=link.remote.name)
        if not remote_intf:
            if lag:
                # this is a member interface, which means it's a physical interface,
                # which means it should already exist in nautobot, as part of the device type
                # if this interface doesn't already exist in nautobot, something has gone very wrong
                raise ValueError(
                    f"Interface {link.remote.name} on {link.remote.device.name}, identified as being "
                    f"connected to {link.local.name} on {link.local.device.name} does not exist in Nautobot."
                    f"Are you sure {link.remote.device.name} has been properly set up?"
                )
            logger.info(f"Creating interface {link.remote.name} on {link.remote.device.name}")
            remote_intf = api.dcim.interfaces.create(
                device=link.remote.device.nb.id, name=link.remote.name, type="lag", **remote_intf_data
            )
        else:
            logger.info(f"Found existing interface {link.remote.name} on {link.remote.device.name}")
            remote_intf = t.cast("Interfaces", remote_intf)
            remote_intf.update(remote_intf_data)

    _get_or_create_intfs(lldp_data.spine2.lag_to_dist)
    _get_or_create_intfs(lldp_data.spine1.lag_to_dist)
    # do spine1 after spine2, so the dist-switch lag label points to spine1 instead of spine2

    _get_or_create_intfs(lldp_data.spine1.link_to_dist, lag=lldp_data.spine1.lag_to_dist)
    _get_or_create_intfs(lldp_data.spine2.link_to_dist, lag=lldp_data.spine2.lag_to_dist)
    for link in lldp_data.spine1.mlag_peers:
        # create the mlag peer lag
        peer_lag = Link(
            local=InterfaceRecord(device=lldp_data.spine1, name="Port-Channel2"),
            remote=InterfaceRecord(device=lldp_data.spine2, name="Port-Channel2"),
        )
        _get_or_create_intfs(peer_lag, peer_link=True)
        _get_or_create_intfs(link, peer_link=True, lag=peer_lag)
    # lldp_data.spine2.mlag_peers is the same list as lldp_data.spine1.mlag_peers,
    # so we don't need to do it again

    for leaf in lldp_data.leafs:
        assert leaf.link_to_spine1 is not None
        assert leaf.link_to_spine2 is not None

        # identify the port channel used by the spines to connect to the leaf. Each leaf has its own
        # ie a3-ev0c-arista has Po3, a4-ev0c-arista has Po4, etc
        spine_lag_number = leaf.name[1:].split("-")[0]

        # create the lags to each spine
        spine1_lag_link = Link(
            local=InterfaceRecord(device=leaf, name="Port-Channel1"),
            remote=InterfaceRecord(device=lldp_data.spine1, name=f"Port-Channel{spine_lag_number}"),
        )
        _get_or_create_intfs(spine1_lag_link)
        spine2_lag_link = Link(
            local=InterfaceRecord(device=leaf, name="Port-Channel1"),
            remote=InterfaceRecord(device=lldp_data.spine2, name=f"Port-Channel{spine_lag_number}"),
        )
        _get_or_create_intfs(spine2_lag_link)

        _get_or_create_intfs(leaf.link_to_spine1, lag=spine1_lag_link)
        _get_or_create_intfs(leaf.link_to_spine2, lag=spine2_lag_link)

    logger.success("All links created/updated successfully.")


def push_nautobot_config_to_switches(*arista_switch_names: str):
    """
    Given a list of switch hostnames, pull ip_address and intended config from Nautobot
    push config to switch via SSH
    """
    from .nornir import get_nornir, F, Task, BaseConnection
    from .nautobot import get_intended_config
    import re

    logger.info(f"Generating fresh Intended Configs for: {arista_switch_names}")
    configs = {sw: get_intended_config(sw) for sw in arista_switch_names}

    arista_switches = get_nornir(concurrent=False).filter(F(name__in=arista_switch_names))

    def update_config(task: Task):
        """
        This function is run on each switch to merge intended config from nautobot into the running config.
        """
        host = task.host
        ssh: BaseConnection = host.get_connection("netmiko", task.nornir.config)

        config = configs[host.name]

        # netmiko is supposed to automatically handle the banner motd, but it doesn't, for some reason
        # so we extract the banner out of the config and handle it ourselves
        logger.info(f"Processing config for {host.name}...")
        banner = re.search(r"^banner motd\n.*\nEOF", config, re.MULTILINE | re.DOTALL)
        assert banner
        banner = banner.group(0)

        config = config.replace(banner, "")

        ssh.enable()
        ssh.timeout = 5
        ssh.config_mode(f"configure session nautobot_{str(hash(config))[-4:]}")
        logger.info(f"{host.name} is now in config mode, pushing configuration commands...")
        try:
            ssh.send_command(
                banner,
                cmd_verify=False,
            )
            ssh.send_config_set(
                config.splitlines(),
                exit_config_mode=False,
                error_pattern=r"%.*",
            )
        except Exception as e:
            logger.error(f"Failed to push config to switch {host.name}: {e}")
            ssh.exit_config_mode("abort")
            raise e
        ssh.exit_config_mode("commit")
        ssh.send_command("write memory")
        logger.success(f"Config pushed to {host.name}")

    arista_switches.run(update_config, raise_on_error=True)
    logger.success(f"Successfully pushed intended configs to switches: {', '.join(arista_switch_names)}")


@t.no_type_check
def _cvp_onboarding():
    # This function was an excercise in frustration, and an attempt to figure out how to use the CVP gRPC API
    # to automate provisioning of a switch through cloudvision itself.
    # it was abandoned when we found out that the sections of the CVP API we needed to use were
    # simultaneously difficult to use, poorly documented, and primed to be deprecated/replaced
    # with something else in the next software release.
    # The code below is a mess, and should not be used as an example of how to use the CVP gRPC API.
    # It is here for reference only, and may be removed in the future.
    from .arista import Settings
    from uoft_core.api import APIBase
    import grpc
    from google.protobuf import wrappers_pb2 as protobuf
    from fmp import wrappers_pb2 as fmp_protobuf
    from arista.studio.v1 import services as studio_svc, models as studio_models
    from arista.workspace.v1 import workspace_pb2 as workspace_models, services as workspace_svc

    class GRPC:
        def __init__(self, token):
            self.channel = grpc.secure_channel(
                target="www.cv-prod-na-northeast1-b.arista.io:443",
                credentials=grpc.composite_channel_credentials(
                    grpc.ssl_channel_credentials(),
                    grpc.access_token_call_credentials(token),
                ),
            )

            # --- studio_svc ServiceStub wrappers ---
            class AssignedTags:
                nonlocal self
                stub = studio_svc.AssignedTagsServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.AssignedTagsStreamRequest())

            self.AssignedTags = AssignedTags

            class AssignedTagsConfig:
                nonlocal self
                stub = studio_svc.AssignedTagsConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.AssignedTagsConfigStreamRequest())

            self.AssignedTagsConfig = AssignedTagsConfig

            class AutofillAction:
                nonlocal self
                stub = studio_svc.AutofillActionServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.AutofillActionStreamRequest())

            self.AutofillAction = AutofillAction

            class AutofillActionConfig:
                nonlocal self
                stub = studio_svc.AutofillActionConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.AutofillActionConfigStreamRequest())

            self.AutofillActionConfig = AutofillActionConfig

            class Inputs:
                nonlocal self
                stub = studio_svc.InputsServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.InputsStreamRequest())

                @classmethod
                def get_one(cls, studio_id, workspace_id, paths: list[str]):
                    return cls.stub.GetOne(
                        studio_svc.InputsRequest(
                            key=studio_models.InputsKey(
                                studio_id=protobuf.StringValue(value=studio_id),
                                workspace_id=protobuf.StringValue(value=workspace_id),
                                path=fmp_protobuf.RepeatedString(values=paths),
                            )
                        )
                    )

            self.Inputs = Inputs

            class InputsConfig:
                nonlocal self
                stub = studio_svc.InputsConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.InputsConfigStreamRequest())

            self.InputsConfig = InputsConfig

            class SecretInput:
                nonlocal self
                stub = studio_svc.SecretInputServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.SecretInputStreamRequest())

            self.SecretInput = SecretInput

            class Studio:
                nonlocal self
                stub = studio_svc.StudioServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.StudioStreamRequest())

            self.Studio = Studio

            class StudioConfig:
                nonlocal self
                stub = studio_svc.StudioConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls) -> t.Generator[studio_svc.StudioConfigStreamResponse, None, None]:
                    return cls.stub.GetAll(studio_svc.StudioConfigStreamRequest())

            self.StudioConfig = StudioConfig

            class StudioSummary:
                nonlocal self
                stub = studio_svc.StudioSummaryServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(studio_svc.StudioSummaryStreamRequest())

            self.StudioSummary = StudioSummary

            # --- workspace_svc ServiceStub wrappers ---
            class Workspace:
                nonlocal self
                stub = workspace_svc.WorkspaceServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(workspace_svc.WorkspaceStreamRequest())

                @classmethod
                def get_one(cls, workspace_id):
                    return cls.stub.GetOne(
                        workspace_svc.WorkspaceStreamRequest(
                            partial_eq_filter=[
                                workspace_models.Workspace(
                                    key=workspace_models.WorkspaceKey(
                                        workspace_id=protobuf.StringValue(value=workspace_id)
                                    )
                                )
                            ]
                        )
                    )

            self.Workspace = Workspace

            class WorkspaceBuild:
                nonlocal self
                stub = workspace_svc.WorkspaceBuildServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(workspace_svc.WorkspaceBuildStreamRequest())

            self.WorkspaceBuild = WorkspaceBuild

            class WorkspaceConfig:
                nonlocal self
                stub = workspace_svc.WorkspaceConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(workspace_svc.WorkspaceConfigStreamRequest())

            self.WorkspaceConfig = WorkspaceConfig

            class WorkspaceSyncConfig:
                nonlocal self
                stub = workspace_svc.WorkspaceSyncConfigServiceStub(self.channel)

                @classmethod
                def get_all(cls):
                    return cls.stub.GetAll(workspace_svc.WorkspaceSyncConfigStreamRequest())

            self.WorkspaceSyncConfig = WorkspaceSyncConfig

    class CVPAPI(APIBase):
        def __init__(self, token):
            super().__init__(base_url="https://cv-prod-na-northeast1-b.arista.io", api_root="/api")
            self.cookies.update({"access_token": token})
            self.headers.update({"Authorization": f"Bearer {token}"})
            self._grpc = None

        @property
        def grpc(self):
            if not self._grpc:
                self._grpc = GRPC(self.cookies["access_token"])
            return self._grpc

    cvp_token = Settings.from_cache().cvp_token.get_secret_value()
    cvp_api = CVPAPI(cvp_token)

    # TODO: check AutofillAction and AutofillActionConfig for a1-ev0c-arista
    # /cvpserver/inventory was a bust
    # StudioService was a bust
    # StudioConfigServer was a bust, but will be useful later
    # StudioSummaryService was a bust
    # inventory.DeviceService was a bust
    # inventory.DeviceOnboarding was a bust
    # inventory.DeviceOnboardinConfig - couldn't figure it out
    # InputsService - ALMOST there, has exactly what we need, but does not include a1-ev0c-arista
    # InputsConfigService - This is the endpoint we need to submit the data to
    # studio_topology.* - I'll be honest, i got lost here. there's so many services,
    # with no clear indication of what they do or how to use them
    r = list([r.value for r in cvp_api.grpc.AutofillAction.get_all()])
    r2 = list([r.value for r in cvp_api.grpc.AutofillActionConfig.get_all()])
    print(r)
    print(r2)
    id = next(iter(cvp_api.grpc.StudioConfig.get_all())).value.key.studio_id.value
    id == "TOPOLOGY"
    # topology_schema = cvp_api.get("/resources/studio/v1/StudioConfig",
    #   params={'key.studioId': 'TOPOLOGY', 'key.workspaceId': 'builtin-studios-v0.99-topology'})
    # topology_schema = topology_schema.json()['value']['inputSchema']

    # grpc_channel = grpc.secure_channel(
    #     target="www.cv-prod-na-northeast1-b.arista.io:443",
    #     credentials=grpc.composite_channel_credentials(
    #         grpc.ssl_channel_credentials(), grpc.access_token_call_credentials(access_token=cvp_token)
    #     ),
    # )
    # studio_config_stub = studio_svc.StudioConfigServiceStub(grpc_channel)
    # workspace_config_stub = workspace_svc.WorkspaceServiceStub(grpc_channel)

    my_workspace = cvp_api.grpc.Workspace.get_one(workspace_id="a1-ev0c-arista")
    topology_studio = cvp_api.grpc.Studio.get_one(studio_id="TOPOLOGY")
    print(my_workspace, topology_studio)
    # assert 'TOPOLOGY' in studios_by_id, "TOPOLOGY studio not found in CVP"
    # topology_studio = studios_by_id['TOPOLOGY']

    return r


def _debug():
    # initial_provision('a3-ev0c-arista', 't1-ev0c', 3)
    # push_nautobot_config_to_switches(
    #     "a1-ev0c-arista",
    #     "a2-ev0c-arista",
    #     "a3-ev0c-arista",
    # )
    pass
