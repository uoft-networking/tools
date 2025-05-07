from time import sleep
from typing import TYPE_CHECKING, Generator, no_type_check

from pexpect import TIMEOUT
from pynautobot import RequestError
from uoft_ssh.cli import get_ssh_session
from uoft_ssh import Settings as SSHSettings
from uoft_core import logging

if TYPE_CHECKING:
    from uoft_ssh.pexpect_utils import UofTPexpectSpawn
    from pynautobot.models.dcim import Devices

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
    from google.protobuf.duration_pb2 import Duration
    from . import enrollment_pb2 as pb
    from . import Settings

    request_serializer = pb.AddEnrollmentTokenRequest.SerializeToString  # pyright: ignore[reportAttributeAccessIssue]
    response_deserializer = pb.AddEnrollmentTokenResponse.FromString  # pyright: ignore[reportAttributeAccessIssue]

    token_request = pb.AddEnrollmentTokenRequest(  # pyright: ignore[reportAttributeAccessIssue]
        enrollmentToken=pb.EnrollmentToken(  # pyright: ignore[reportAttributeAccessIssue]
            validFor=Duration(seconds=60 * 60 * 4)  # 4 hours
        )
    )

    s = Settings.from_cache()

    credentials = grpc.composite_channel_credentials(
        grpc.ssl_channel_credentials(),
        grpc.access_token_call_credentials(s.cvp_token.get_secret_value()),
    )
    # Create a gRPC channel
    channel = grpc.secure_channel(target="www.cv-prod-na-northeast1-b.arista.io:443", credentials=credentials)

    grpc_method = channel.unary_unary(
        "/admin.Enrollment/AddEnrollmentToken",
        request_serializer=request_serializer,
        response_deserializer=response_deserializer,
    )

    resp = grpc_method(request=token_request)
    return resp.enrollmentToken.token


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
        decoder = ssh._decoder  # type: ignore
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
        logger.info("This appears to be a partially initialized switch. Logging in now...")
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


def _get_intended_config_from_nautobot(switch_hostname: "str | Devices") -> str:
    from ..nautobot import get_api, run_job

    nb = get_api(dev=False)
    if not isinstance(switch_hostname, str):
        switch = nb.dcim.devices.get(name=switch_hostname)
    else:
        switch = switch_hostname
    try:
        intended_config: str = nb.plugins.golden_config.config_postprocessing.get(switch.id).config  # type: ignore
    except RequestError:
        # trigger intended config generation
        logger.info(f"Switch {switch_hostname} does not have an intended config, generating one now...")
        run_job(dev=False, job_name="Generate Intended Configurations", data=dict(device=[switch.id]))  # type: ignore
        intended_config: str = nb.plugins.golden_config.config_postprocessing.get(switch.id).config  # type: ignore
    return intended_config


def _get_minimum_viable_config(switch_hostname: str) -> list[str]:
    from ..nautobot import filter_config

    intended_config = _get_intended_config_from_nautobot(switch_hostname)
    res = filter_config(
        config=intended_config,
        filters=[
            "hostname",
            "radius-server",
            "ip radius",
            "ip address",
            "ip route",
            "enable",
        ],
    )
    res.extend(
        filter_config(
            config=intended_config,
            filters=[
                "aaa",
                "interface Management1",
                "management ssh",
            ],
            sub_filters=[
                "server",  # for `aaa group`
                "ip address",  # for `interface Management1`
                "authentication",  # for `management ssh`
            ],
        )
    )
    return res


def onboard_via_terminal_server(switch_hostname: "str | Devices", terminal_server: str, port: int):
    from ..nautobot import get_api, filter_config

    nb = get_api(dev=False)
    if isinstance(switch_hostname, str):
        switch = nb.dcim.devices.get(name=switch_hostname)
    else:
        switch = switch_hostname
    if not switch:
        logger.error(f"Switch {switch_hostname} not found in Nautobot")
        return

    mgmt_intf = nb.dcim.interfaces.get(device=switch.id, name="Management1")  # type: ignore
    if not mgmt_intf:
        logger.error(f"Switch {switch_hostname} does not have a Management1 interface")
        return
    if not mgmt_intf.enabled:  # type: ignore
        logger.info(f"Enabling Management1 interface on {switch_hostname}")
        mgmt_intf.update(dict(enabled=True))  # type: ignore
    if len(mgmt_intf.ip_addresses) == 0:  # type: ignore
        logger.warning(f"Switch {switch_hostname} does not have an OOB IP address assigned")
        oob_pfx = nb.ipam.prefixes.get(prefix="192.168.64.0/22")
        logger.warning(f"Assigning next available IP to {switch_hostname}")
        oob_ip = oob_pfx.available_ips.create(  # type: ignore
            data=dict(status="Active", dns_name=f"{switch_hostname}-oob", description=f"{switch_hostname}-oob")
        )
        nb.ipam.ip_address_to_interface.create(dict(ip_address=oob_ip.id, interface=mgmt_intf.id))  # type: ignore
        switch.update(dict(primary_ip4=oob_ip.id))  # type: ignore
        logger.info(f"Assigned IP {oob_ip.address} to {switch_hostname}")
    else:
        oob_ip = mgmt_intf.ip_addresses[0]  # type: ignore

    onboarding_token = get_onboarding_token()

    ssh = _get_ssh_session(terminal_server, port)

    _put_switch_in_config_mode(ssh)

    logger.info("Switch is now in config mode, ready to accept configuration commands.")

    # At this point, we want to deploy only the minimum viable config to the switch necessary to get it
    # online and accessible via SSH (including RADIUS auth)

    # The rest of the config can then be deployed via Nornir/SSH, much faster and more reliable than
    # trying to do it all in one go here

    # rather than try to replicate and recreate the minimum viable bits of config here, (including RADIUS keys, etc)
    # we will get the full intended config from nautobot, and filter it down to just the lines we want / care about
    intended_config = _get_intended_config_from_nautobot(switch_hostname)

    logger.info("Setting up admin and enable passwords...")
    admin_pw = SSHSettings.from_cache().admin.password.get_secret_value()
    ssh.sendline(f"username admin privilege 15 role network-admin secret {admin_pw}")
    enable_pw = SSHSettings.from_cache().enable_secret.get_secret_value()
    ssh.sendline(f"enable password {enable_pw}")

    logger.info(f"Setting hostname to {switch_hostname}")
    ssh.sendline(f"hostname {switch_hostname}")

    # logger.info("Setting DNS servers...")
    # ssh.sendline("ip name-server 142.1.96.4 142.1.96.3")

    logger.info(f"Setting OOB ip address to {oob_ip.address}")
    ssh.sendline("interface Management1")
    ssh.sendline(f"ip address {oob_ip.address}")
    ssh.sendline("no shutdown")
    ssh.sendline("exit")

    logger.info("Setting default gateway...")
    ssh.sendline("ip route 0.0.0.0/0 192.168.64.1")

    # logger.info("Enabling SSH...")
    # ssh.sendline("management ssh")
    # ssh.sendline("authentication mode password")  # bare minimum required to get SSH working

    #logger.info("Setting up RADIUS auth...")

    # logger.info("Writing CVP onboarding token to file...")
    # ssh.sendline("copy terminal: file:/tmp/cv-onboarding-token")
    # ssh.expect("enter input")
    # ssh.sendline(onboarding_token)
    # ssh.sendline("")
    # ssh.sendcontrol("d")
    # ssh.expect("Copy completed")

    # logger.info("Configuring TerminAttr daemon...")
    # ssh.sendline("daemon TerminAttr")
    # ssh.sendline(
    #     "exec /usr/bin/TerminAttr -smashexcludes=ale,flexCounter,hardware,kni,pulse,strata "
    #     "-cvaddr=apiserver.arista.io:443 -cvauth=token-secure,/tmp/cv-onboarding-token "
    #     "-cvproxy=http://dante.utsc.utoronto.ca:3128 -taillogs --disableaaa"
    # )
    # ssh.sendline("no shutdown")

    logger.success(
        "Switch is now ready for onboarding. It can be accessed via SSH with the admin "
        f"account at IP address {oob_ip.address} and should show up in CVP momentarily"
    )
    ssh.sendline("wr mem")


def push_nautobot_config_to_switch(switch_hostname: str):
    """
    Given a switch hostname, pull ip_address and intended config from Nautobot
    push config to switch via SSH
    """
    from ..nautobot import get_api

    nb = get_api(dev=False)
    switch = nb.dcim.devices.get(name=switch_hostname)

    if not switch:
        raise ValueError(f"Switch {switch_hostname} not found in Nautobot")

    s = SSHSettings.from_cache()

    try:
        ip = switch.primary_ip4.address.split("/")[0]  # type: ignore
    except Exception as e:
        logger.error(f"Switch {switch_hostname} does not have a primary IP address")
        raise ValueError(f"Switch {switch_hostname} does not have a primary IP address") from e
    logger.info(f"Switch {switch_hostname} has IP address {ip}")

    intended_config = _get_intended_config_from_nautobot(switch_hostname)
    _wait_for_switch_to_come_online(ip)

    ssh = get_ssh_session(
        host=ip,
        username=s.admin.username,
        password=s.admin.password.get_secret_value(),
        accept_unknown_host=True,
    )

    _put_switch_in_config_mode(ssh)

    for line in intended_config.splitlines():
        if line.startswith("!"):
            continue
        if line == "":
            continue
        logger.debug(f"Sending command: {line}")
        ssh.sendline(line)
        res = ssh.expect([r"%.*", TIMEOUT], timeout=0.5)
        if res == 0:
            logger.error(f"Command {line} failed with error: {ssh.after}")
            raise RuntimeError(f"Command {line} failed with error: {ssh.after}")

    logger.info("Config pushed to switch successfully. Writing config to flash...")
    ssh.sendline("write memory")
    ssh.expect(r"#")
    logger.info("Config written to flash successfully.")
    ssh.sendline("end")
    ssh.sendline("exit")
    ssh.close()
    logger.success(f"Config pushed to {switch_hostname} successfully.")


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


@no_type_check
def _cvp_onboarding():
    # This function was an excercise in frustration, and an attempt to figure out how to use the CVP gRPC API
    # to automate provisioning of a switch through cloudvision itself.
    # it was abandoned when we found out that the sections of the CVP API we needed to use were
    # simultaneously difficult to use, poorly documented, and primed to be deprecated/replaced
    # with something else in the next software release.
    # The code below is a mess, and should not be used as an example of how to use the CVP gRPC API.
    # It is here for reference only, and may be removed in the future.
    from . import Settings
    from uoft_core.api import APIBase
    import grpc
    from google.protobuf import wrappers_pb2 as protobuf  # noqa
    from fmp import wrappers_pb2 as fmp_protobuf  # noqa
    from arista.studio.v1 import services as studio_svc, models as studio_models  # noqa
    from arista.workspace.v1 import workspace_pb2 as workspace_models, services as workspace_svc  # noqa

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
                def get_all(cls) -> Generator[studio_svc.StudioConfigStreamResponse, None, None]:
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
    # studio_topology.* - I'll be honest, i got lost here. there's so many services, with no clear indication of what they do or how to use them
    r = list([r.value for r in cvp_api.grpc.AutofillAction.get_all()])
    r2 = list([r.value for r in cvp_api.grpc.AutofillActionConfig.get_all()])
    print(r)
    id = next(iter(cvp_api.grpc.StudioConfig.get_all())).value.key.studio_id.value
    id == "TOPOLOGY"
    # topology_schema = cvp_api.get("/resources/studio/v1/StudioConfig", params={'key.studioId': 'TOPOLOGY', 'key.workspaceId': 'builtin-studios-v0.99-topology'})
    # topology_schema = topology_schema.json()['value']['inputSchema']

    # grpc_channel = grpc.secure_channel(
    #     target="www.cv-prod-na-northeast1-b.arista.io:443",
    #     credentials=grpc.composite_channel_credentials(
    #         grpc.ssl_channel_credentials(), grpc.access_token_call_credentials(access_token=cvp_token)
    #     ),
    # )
    # studio_config_stub = studio_svc.StudioConfigServiceStub(grpc_channel)
    # workspace_config_stub = workspace_svc.WorkspaceServiceStub(grpc_channel)

    # my_workspace = workspace_config_stub.GetOne(workspace_svc.WorkspaceStreamRequest(partial_eq_filter=workspace_models.WorkspaceConfig(display_name=protobuf.StringValue('config a1-ev0c-arista'))), timeout=60)
    # topology_studio = studio_config_stub.GetOne(studio_svc.StudioConfigRequest(key=studio_models.StudioKey(studio_id=protobuf.StringValue(value="TOPOLOGY"), workspace_id=protobuf.StringValue(value="builtin-studios-v0.99-topology"))), timeout=60)

    # all_studios: list[studio_svc.StudioConfigStreamResponse] = studio_config_stub.GetAll(studio_svc.StudioConfigStreamRequest(), timeout=60)
    # studios_by_id = {res.value.key.studio_id.value: res.value for res in all_studios}

    # my_studios = studio_config_stub.GetAll(studio_svc.StudioConfigStreamRequest(partial_eq_filter=[studio_models.StudioConfig(key=studio_models.StudioKey(workspace_id=key_ev0c_test))]), timeout=60)
    # my_studios: list[studio_models.StudioConfig] = [res.value for res in my_studios] # type: ignore[assignment]

    # assert 'TOPOLOGY' in studios_by_id, "TOPOLOGY studio not found in CVP"
    # topology_studio = studios_by_id['TOPOLOGY']

    return r


def _debug():
    res = _get_minimum_viable_config("a1-ev0c-arista")
    print("\n".join(res))
    # onboard_via_terminal_server("a1-ev0c-arista", "t1-ev0c", 1)
    # arista_wipe_switch("t1-ev0c", 1)
