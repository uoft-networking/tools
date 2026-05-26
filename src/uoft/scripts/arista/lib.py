from dataclasses import dataclass
from functools import cached_property
from time import sleep
import typing as t
import os

from pexpect import TIMEOUT
from uoft.core.console import console
from uoft.ssh.util import get_ssh_session
from uoft.ssh.conf import Settings as SSHSettings
from uoft.core import logging
from uoft.core import BaseSettings, SecretStr
from netmiko.exceptions import ConfigInvalidException, ReadTimeout

from ..base import interface_name_normalize, interface_name_denormalize


if t.TYPE_CHECKING:
    from uoft.ssh.pexpect_utils import UofTPexpectSpawn
    from pynautobot.models.dcim import Devices, Interfaces


class Settings(BaseSettings):
    cvp_token: SecretStr

    class Config(BaseSettings.Config):
        app_name = "arista"


logger = logging.getLogger(__name__)

TERM_SRV_TYP = t.Literal["tripplite", "airconsole"]


def _terminal_server_ssh_session(
    terminal_server: str,
    port: int,
    terminal_server_type: TERM_SRV_TYP = "tripplite",
):
    if terminal_server_type == "airconsole":
        # airconsole encodes the serial port number into the SSH port number,
        # runs a separate SSH server for each port
        creds = SSHSettings.from_cache().airconsole
        username = creds.username
        extra_args = ["-p", f"40{port:02d}"]  # Airconsole uses port numbers like 4001, 4002, etc.
    else:
        # tripplite terminal servers encode the serial port number into SSH username
        # using the username format <username>:port<port>
        creds = SSHSettings.from_cache().terminal_server
        username = f"{creds.username}:port{port}"
        extra_args = []

    ssh = get_ssh_session(
        host=terminal_server,
        username=username,
        password=creds.password.get_secret_value(),
        extra_args=extra_args,
    )

    return ssh


def _get_onboarding_token():
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

    return res.enrollmentToken.token  # pyright: ignore[reportAttributeAccessIssue]


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


def initial_provision(
    switch_hostname: str, terminal_server: str, port: int, terminal_server_type: TERM_SRV_TYP = "tripplite"
):
    """
    Given a switch hostname, terminal server, and port,
    connect to the switch via the terminal server
    and give it the minimum viable config necessary
    to get it online and accessible via SSH over OOB
    (including RADIUS auth)
    """
    from ..nautobot import get_minimum_viable_config
    from ..nautobot.lib import get_or_assign_oob_ip
    from rich.progress import track

    oob_ip = get_or_assign_oob_ip(switch_hostname)

    ssh = _terminal_server_ssh_session(terminal_server, port, terminal_server_type)

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
        res = ssh.expect([r"%.*#", TIMEOUT], timeout=0.5)
        if res == 0:
            logger.error(f"Command {line} failed with error: {ssh.after}")
            raise RuntimeError(f"Command {line} failed with error: {ssh.after}")

    logger.success(
        "Switch is now ready for onboarding. It can be accessed via SSH with the admin "
        f"account at IP address {oob_ip} and should show up in CVP momentarily"
    )
    ssh.sendline("wr mem")


def onboard_into_cvp(switch_name: str, oob=True):
    s = SSHSettings.from_cache()
    logger.info(f"Onboarding switch {switch_name} into CVP...")
    ssh = get_ssh_session(
        switch_name,
        username=s.personal.username,
        password=s.personal.password.get_secret_value(),
        accept_unknown_host=True,
    )
    onboarding_token = _get_onboarding_token()

    ssh.expect(r"([a-zA-Z0-9-]+)>")
    # entering config mode
    ssh.sendline("enable")
    ssh.sendline(s.enable_secret.get_secret_value())
    ssh.expect(r"([a-zA-Z0-9-]+)#")
    ssh.sendline("configure terminal")
    ssh.expect(r"([a-zA-Z0-9-]+)\(config\)#")

    logger.info("Writing CVP onboarding token to file...")
    ssh.sendline("copy terminal: file:/tmp/cv-onboarding-token")
    ssh.expect("enter input")
    ssh.sendline(onboarding_token)
    ssh.sendline("")
    ssh.sendcontrol("d")
    ssh.expect("Copy completed")

    logger.info("Configuring TerminAttr daemon...")
    ssh.expect(r"([a-zA-Z0-9-]+)\(config\)#")
    ssh.sendline("daemon TerminAttr")
    cmd = (
        "exec /usr/bin/TerminAttr -smashexcludes=ale,flexCounter,hardware,kni,pulse,strata "
        "-cvaddr=apiserver.arista.io:443 -cvauth=token-secure,/tmp/cv-onboarding-token "
        "-cvproxy=http://dante.utsc.utoronto.ca:3128 -taillogs --disableaaa"
    )
    if oob:
        cmd += " --cvvrf=MANAGEMENT-VRF"
    ssh.sendline(cmd)
    ssh.sendline("shutdown")
    ssh.sendline("no shutdown")
    ssh.expect(r"([a-zA-Z0-9-]+)\(config-daemon-TerminAttr\)#")
    ssh.sendline("end")
    ssh.expect(r"([a-zA-Z0-9-]+)#")
    ssh.sendline("write memory")
    ssh.expect(r"([a-zA-Z0-9-]+)#")
    logger.success("Switch has been onboarded into CVP. It should show up in CVP momentarily.")


def wipe_switch(
    terminal_server: str, port: int, reenable_ztp_mode: bool = False, terminal_server_type: TERM_SRV_TYP = "tripplite"
):
    """
    Given a terminal server and port,
    wipe the Arista switch attached to that port
    and reset it to factory defaults.
    This is used for testing and debugging.
    """
    ssh = _terminal_server_ssh_session(terminal_server, port, terminal_server_type)
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
        from ..nautobot import get_api

        api = get_api(dev=False)
        return api.dcim.devices.get(name=self.name)  # pyright: ignore[reportReturnType]


@dataclass(eq=False, kw_only=True)
class InterfaceRecord:
    device: DeviceRecord
    name: str

    @cached_property
    def nb(self) -> "Interfaces":
        from ..nautobot import get_api

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
        from ..nautobot import get_api

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
    dist_lag_number: int | str = "auto",
) -> LLDPData:
    from ..nautobot import get_api

    api = get_api(dev=False)
    dist = Dist(name=dist_switch_hostname)
    spine1 = Spine(name=arista_switch_names[0], mlag_peers=[], link_to_leafs=[])
    spine2 = Spine(name=arista_switch_names[1], mlag_peers=[], link_to_leafs=[])
    leafs = [Leaf(name=leaf_hostname) for leaf_hostname in arista_switch_names[2:]]

    def _get_or_create_dist_lag(spine_name: str, dist_lag_number: int | str):
        # find the next free port channel number on the dist switch
        # TODO: right now this is cisco-specific, needs to be able to handle arista dist switches too

        label_fragment = spine_name.partition("-")[2]
        # given a spine name like `a1-ev0c-arista`, this will give us `ev0c-arista`
        lags = api.dcim.interfaces.filter(device=dist.nb.id, type="lag")

        if dist_lag_number == "auto":
            if lags and (existing_lag := next((lag for lag in lags if label_fragment in lag.label), None)):  # pyright: ignore[reportAttributeAccessIssue, reportOperatorIssue]
                lag_name = t.cast(str, existing_lag.name)  # pyright: ignore[reportAttributeAccessIssue]
                logger.info(f"Found existing port channel {lag_name} on {dist.name}")
                existing_lag = t.cast("Interfaces", existing_lag)
                return InterfaceRecord(device=dist, name=lag_name)

            lag_numbers = sorted([int(lag.name.partition("hannel")[2]) for lag in lags])  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
            target_lag_number = lag_numbers[-1] + 1 if lag_numbers else 1
        else:
            try:
                target_lag_number = int(dist_lag_number)
            except ValueError:
                raise ValueError(f"dist_lag_number must be an integer or 'auto', got {dist_lag_number}")
        lag_name = f"Port-Channel{target_lag_number}"
        if existing_lag := next((lag for lag in lags if lag.name == lag_name), None):  # pyright: ignore[reportAttributeAccessIssue, reportOperatorIssue]
            logger.info(f"Found existing port channel {lag_name} on {dist.name}")
            return InterfaceRecord(device=dist, name=lag_name)
        logger.info(f"Creating new port channel {target_lag_number} on {dist_switch_hostname} for {label_fragment}")
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
    dist.lag_to_spines = _get_or_create_dist_lag(spine1.name, dist_lag_number)
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

    if len(spine1.mlag_peers) == 0:
        logger.error("No mlag peer links found between spines, this is unexpected!")
        raise ValueError("No mlag peer links found between spines, this is unexpected!")

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


def map_stack_connections(
    dist_switch_hostname: str, *arista_switch_names: str, dist_lag_number: int | t.Literal["auto"] = "auto"
):
    """
    Given a dist switch and a list of arista switches to organize into an mlag leaf-spine stack,
    login to each over ssh, identify connections between them all using LLDP, identify port roles
    for each port of each connection, and push the data to nautobot
    """
    from ..nornir import get_nornir, F, Task, BaseConnection
    from ..nautobot import get_api

    if isinstance(dist_lag_number, str) and dist_lag_number.lower() != "auto":
        try:
            dist_lag_number = int(dist_lag_number)
        except ValueError:
            raise ValueError(f"dist_lag_number must be an integer or 'auto', got {dist_lag_number}")

    nr = get_nornir()

    nr = nr.filter(F(name__in=[dist_switch_hostname, *arista_switch_names]))

    lldp_data_raw = dict()

    def get_lldp_data(task: Task):
        host = task.host
        ssh: BaseConnection = task.host.get_connection("netmiko", task.nornir.config)
        res = ssh.send_command("show lldp neighbors", use_textfsm=True)
        lldp_data_raw[host.name] = res

    nr.run(get_lldp_data)

    lldp_data = _parse_lldp_data(
        lldp_data_raw, dist_switch_hostname, arista_switch_names, dist_lag_number=dist_lag_number
    )

    assert lldp_data.dist.link_to_spine1 is not None, "Dist switch is not connected to spine1"
    assert lldp_data.dist.link_to_spine2 is not None, "Dist switch is not connected to spine2"
    assert lldp_data.dist.lag_to_spines is not None, "Dist switch is not connected to spines via a lag interface"
    assert lldp_data.spine1.link_to_dist is not None, "Spine1 is not connected to dist switch"
    assert lldp_data.spine2.link_to_dist is not None, "Spine2 is not connected to dist switch"
    assert lldp_data.spine1.lag_to_dist is not None, "Spine1 is not connected to dist switch via a lag interface"
    assert lldp_data.spine2.lag_to_dist is not None, "Spine2 is not connected to dist switch via a lag interface"
    assert lldp_data.spine1.mlag_peers is not None
    assert lldp_data.spine2.mlag_peers is not None
    assert lldp_data.spine1.link_to_leafs is not None, "Spine1 is not connected to any leaf switches"
    assert lldp_data.spine2.link_to_leafs is not None, "Spine2 is not connected to any leaf switches"
    assert lldp_data.leafs is not None, "No leaf switches found"

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
        assert leaf.link_to_spine1 is not None, f"Leaf {leaf.name} is not connected to spine1"
        assert leaf.link_to_spine2 is not None, f"Leaf {leaf.name} is not connected to spine2"

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
    from ..nornir import get_nornir, F, Task, BaseConnection, Result
    from ..nautobot import get_intended_config
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
            logger.error(f"Failed to push config to switch {host.name}, aborting config session.")
            ssh.exit_config_mode("abort")
            if isinstance(e, ConfigInvalidException):
                return Result(host, f"Config for {host.name} is invalid: {e.with_traceback(None)}", failed=True)
            raise e
            ssh.exit_config_mode("commit")
        ssh.send_command("write memory")
        return Result(host, f"Config pushed to {host.name}", changed=True)

    arista_switches.run(update_config, raise_on_error=True)
    logger.success(f"Successfully pushed intended configs to switches: {', '.join(arista_switch_names)}")


def breakout_interface(switch_name: str, interface_name: str):
    """
    Given a switch name and a list of interfaces to breakout,
    update the switch's interfacees in nautobot to reflect the breakout

    ie, if interfaces = ['Ethernet97/1'], connect to Nautobot
    - find Ethernet97/1, set its type to SFP28 (25GE),
    - create Ethernet97/2, Ethernet97/3, Ethernet97/4 with type SFP28 (25GE),
    """
    from ..nautobot import get_api, Record

    nb = get_api(dev=False)
    switch: Record | None = nb.dcim.devices.get(name=switch_name) # pyright: ignore[reportAssignmentType]
    if not switch:
        raise ValueError(f"Switch {switch_name} not found in Nautobot")

    interface: Record | None = nb.dcim.interfaces.get(device=switch.id, name=interface_name) # pyright: ignore[reportAssignmentType]
    if not interface:
        raise ValueError(f"Interface {interface_name} not found on switch {switch_name}")

    # update the interface type to SFP28 (25GE)
    logger.info(f"Updating {interface_name} on {switch_name} to SFP28 (25GE)")
    interface.update(dict(type="25gbase-x-sfp28"))

    # create the new interfaces
    base_name = interface_name.rpartition("/")[0]
    for i in range(2, 5):
        new_interface_name = f"{base_name}/{i}"
        if nb.dcim.interfaces.get(device=switch.id, name=new_interface_name): # pyright: ignore[reportArgumentType]
            logger.info(f"Interface {new_interface_name} already exists on {switch_name}, skipping creation")
            continue
        logger.info(f"Creating interface {new_interface_name} on {switch_name} with type SFP28 (25GE)")
        nb.dcim.interfaces.create(
            dict(
                device=switch.id,
                name=new_interface_name,
                type="25gbase-x-sfp28",
                status="Active",
            )
        )

    logger.success(f"Successfully broke out 100G {interface_name} on {switch_name} into 4 x 25G interfaces")


@t.no_type_check
def _cvp_onboarding():
    # This function was an excercise in frustration, and an attempt to figure out how to use the CVP gRPC API
    # to automate provisioning of a switch through cloudvision itself.
    # it was abandoned when we found out that the sections of the CVP API we needed to use were
    # simultaneously difficult to use, poorly documented, and primed to be deprecated/replaced
    # with something else in the next software release.
    # The code below is a mess, and should not be used as an example of how to use the CVP gRPC API.
    # It is here for reference only, and may be removed in the future.
    from .lib import Settings
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
