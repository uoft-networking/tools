from nautobot.apps import jobs
from nautobot.dcim.models import Device, Interface
from nautobot.extras.models import Role
from nautobot.ipam.models import VLAN


@jobs.register_jobs
class PortActivationJob(jobs.Job):
    """
    Job to activate ports on a device.
    """

    grouping = "University of Toronto" # pyright: ignore[reportAssignmentType]

    class Meta(jobs.Job.Meta):
        name = "Port Activation"
        description = "Activate ports on a specified device."
        has_sensitive_variables = False
        

    device = jobs.ObjectVar(
        label="Device",
        model=Device,
    )

    interface = jobs.ObjectVar(
        label="Interface",
        model=Interface,
        query_params={"device_id": "$device"},
    )

    role = jobs.ObjectVar(
        label="Role",
        model=Role,
        query_params={"content_types": "dcim.interface"},
    )

    vlan = jobs.ObjectVar(
        label="VLAN",
        model=VLAN,
        query_params={"vlan_group": "$device.vlan_group"},
    )

    def run(self, device, interface, role, vlan):
        return f"Activating interface {interface.name} on device {device.name} with role {role.name} and VLAN {vlan.vid}."


jobs = [PortActivationJob]
