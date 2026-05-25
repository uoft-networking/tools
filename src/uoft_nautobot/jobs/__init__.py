from nautobot.apps import jobs as j
from nautobot.dcim.models import Device, Interface
from nautobot.extras.models import Role
from nautobot.ipam.models import VLAN
from django.conf import settings

from uoft_scripts import interface_name_normalize


class EscalationRequired(Exception):
    """Exception raised when escalation is required for port activation."""
    pass


class HelpdeskPortActivation(j.Job):
    """
    Job to allow helpdesk staff to activate certain kinds of ports on devices.
    """

    grouping = "University of Toronto"  # pyright: ignore[reportAssignmentType]

    class Meta(j.Job.Meta):
        name = "Helpdesk Port Activation"
        description = "Attempt to activate aport on a specified device."
        has_sensitive_variables = False

    device = j.StringVar(
        label="Device",
    )

    interface = j.StringVar(
        label="Interface",
    )

    role = j.ChoiceVar(
        label="Role",
        choices=[
            ("Desktop PC", "Desktop PC"),
            ("VOIP Phone", "VOIP Phone"),
            ("Other", "Other"),
        ],
    )

    port_label = j.StringVar(min_length=5, max_length=100, label="Port label to apply")

    extra_data = j.JSONVar(
        label="Extra Data",
        description="Additional data to store with the interface activation (e.g., raw LLDP data).",
        required=False,
    )

    def run(
        self, device: str, interface: str, role: str, port_label: str, extra_data: dict
    ):
        device_obj = Device.objects.filter(name=device).first()
        if not device_obj:
            raise ValueError(f"Device {device} not found.")
        self.logger.info("Found device: %s", device_obj, extra=dict(object=device_obj))

        interface = interface_name_normalize(interface)
        interface_obj = Interface.objects.filter(
            device=device_obj, name=interface
        ).first()
        if not interface_obj:
            raise ValueError(f"Interface {interface} on device {device} not found.")
        self.logger.info(
            "Found interface: %s", interface_obj, extra=dict(object=interface_obj)
        )

        if role not in ["Desktop PC", "VOIP Phone", "Other"]:
            raise ValueError(
                f"Role {role} is not permitted for helpdesk activation. Valid roles are: Desktop PC, VOIP Phone, Other."
            )

        if role == "Desktop PC":
            vlan = 100
            role_obj = Role.objects.get(name="Access")  # TODO: handle ResNet
        elif role == "VOIP Phone":
            vlan = 306
            role_obj = Role.objects.get(name="VOIP")
        else:
            raise EscalationRequired(
                "'Other' role not yet implemented in HelpdeskPortActivation job."
            )
        self.logger.info("Role selected: %s", role_obj, extra=dict(object=role_obj))

        vlan_obj = VLAN.objects.filter(
            vid=vlan, vlan_group=device_obj.vlan_group
        ).first()
        if not vlan_obj:
            raise ValueError(
                f"VLAN {vlan} not found in VLAN group {device_obj.vlan_group}."
            )
        self.logger.info("Found VLAN: %s", vlan_obj, extra=dict(object=vlan_obj))

        self.logger.info("Port label to apply: %s", port_label)

        # In order to run a job from within another job without breaking nautobot or causing a deadlock,
        # we have to do something gnarly. We have to create a "grafted" job class that inherits from the job we want to run,
        # but is an instance of the current job, so that logging and context are preserved.
        grafted_class = type(
            "GraftedPortActivation",
            (PortActivation, HelpdeskPortActivation),
            self.__dict__,
        )
        return grafted_class().run(
            device=device_obj,
            interface=interface_obj,
            role=role_obj,
            vlan=vlan_obj,
            label=port_label,
        )


class PortActivation(j.Job):
    """
    Job to allow network administrators to activate any port on devices.
    """

    grouping = "University of Toronto"  # pyright: ignore[reportAssignmentType]

    class Meta(j.Job.Meta):
        name = "Port Activation"
        description = "Activate a port on a specified device."
        has_sensitive_variables = False

    device = j.ObjectVar(
        label="Device",
        model=Device,
    )

    interface = j.ObjectVar(
        label="Interface",
        model=Interface,
        query_params={"device_id": "$device"},
    )

    role = j.ObjectVar(
        label="Role",
        model=Role,
        query_params={"content_types": "dcim.interface"},
    )

    vlan = j.ObjectVar(
        label="VLAN",
        model=VLAN,
        query_params={"vlan_group": "$device.vlan_group"},
    )

    label = j.StringVar(min_length=5, max_length=100, label="Port label to apply")

    def run(
        self, device: Device, interface: Interface, role: Role, vlan: VLAN, label: str
    ):
            self.logger.info(
                f"Configuring interface {interface.name} on device {device.name} with role {role.name}, VLAN {vlan.vid}, and label {label}."
            )
        interface.enabled = True
        interface.role = role
        interface.mode = "access"
        interface.label = label
        interface.untagged_vlan = vlan  # pyright: ignore[reportAttributeAccessIssue]
        interface.label = label
        interface.validated_save()
        from nautobot.extras.jobs import JobResult
        JobResult.status
        # I cannot for the life of me, no matter what I try, get Golden Config's IntendedJob to run
        # from within another job properly. So we have to do this the hard way:
        # the closest I ever got was using the grafted class technique above, but that still failed due to some
        # issue with graphql queries deep within the IntendedJob implementation logic.
        # Lucky for us, i already wrote a "clean room" reimplementation of the intended config generation logic
        # for the purpose of testing our templates before commiting them, so we can just borrow that code here.
        from uoft_scripts.nautobot.lib import (
            test_golden_config_templates,
            filter_config,
        )
        from nautobot.extras.models import GitRepository
        from pathlib import Path

        templates_dir = GitRepository.objects.get(
            name="golden_config_templates"
        ).filesystem_path
        templates_dir = Path(templates_dir)

        switch_name = device.name
        assert switch_name is not None, "Device must have a name."
        cfg = test_golden_config_templates(
            device_name=switch_name,
            templates_dir=templates_dir,
            print_output=False,
            dev=settings.DEBUG,
        )
        interface_cfg = filter_config(cfg, [f"interface {interface.name}"])[0]
        self.logger.debug(
            f"Intended configuration for interface {interface.name}:\n{interface_cfg}"
        )

        self.logger.info(
            f"Connecting to device {device.name} via SSH to apply configuration..."
        )

        from netmiko import (
            ConnectHandler,
            BaseConnection,
            NetmikoTimeoutException,
            NetmikoAuthenticationException,
        )
        from .. import Settings

        s = Settings.from_cache()
        if settings.DEBUG:
            ssh_auth = s.ssh.nautobot
        else:
            ssh_auth = s.ssh.personal
        ssh: BaseConnection = ConnectHandler(
            device_type=device.platform.network_driver,  # pyright: ignore[reportAttributeAccessIssue]
            host=str(
                device.primary_ip.address.ip
            ),  # pyright: ignore[reportAttributeAccessIssue]
            username=ssh_auth.username,
            password=ssh_auth.password.get_secret_value(),
            secret=s.ssh.enable_secret.get_secret_value(),
        )

        self.logger.info(
            f"Applying configuration to interface {interface.name} on device {device.name}..."
        )
        ssh.enable()
        ssh.send_config_set(interface_cfg.splitlines())
        self.logger.info(f"Saving configuration on device {device.name}...")
        ssh.save_config()
        ssh.disconnect()

        msg = f"Interface {interface.name} on device {device.name} activated successfully."
        self.logger.success(msg)  # pyright: ignore[reportAttributeAccessIssue]
        return msg


class PortActivationWithApproval(PortActivation):
    """
    Job to allow network administrators to activate any port on devices, with approval required.
    """

    class Meta(PortActivation.Meta):
        name = "Port Activation (Approval Required)"
        description = "Activate a port on a specified device, requiring approval."
        approval_required = True


jobs = [HelpdeskPortActivation, PortActivation, PortActivationWithApproval]
j.register_jobs(*jobs)
