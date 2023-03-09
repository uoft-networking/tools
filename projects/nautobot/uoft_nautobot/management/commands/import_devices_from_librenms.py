from django.core.management.base import BaseCommand
from uoft_core import debug_cache, shell

from librenms_handler.devices import Devices
from librenms_handler.device_groups import DeviceGroups
from librenms_handler.switching import Switching
import re
from nautobot.dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Site,
    Platform,
    Interface,
)
from nautobot.extras.models import Status
from nautobot.ipam.models import IPAddress, VLAN, VLANGroup
from rich.progress import Progress, MofNCompleteColumn


@debug_cache
def fetch_devices_from_librenms():
    url = "https://librenms.server.utsc.utoronto.ca"
    token = shell("pass librenms-api")

    ld = Devices(url, token)

    devices = ld.list_devices(order_type="up").json()["devices"]
    for d in devices:
        res = ld.get_device_groups(d["device_id"]).json()
        if "groups" in res:
            d["groups"] = res["groups"]
        else:
            d["groups"] = []

    return devices


def create_devices():
    devices = fetch_devices_from_librenms()
    pat = re.compile(r"^((av|[ad]\d)-|[sn]dc(vg0\d|-(core|wan|wifi-aggregation-\d)\d)).*")
    devices = list(
        filter(
            lambda d: pat.match(d["hostname"]),
            devices,
        )
    )

    all_sites = {s.name: s for s in Site.objects.all()}
    all_sites["Student Life"] = all_sites["Student Centre"]
    all_sites["Environment Sciences & Chemistry Building"] = all_sites[
        "Environmental Science & Chemistry Building"
    ]

    device_types = {s.part_number: s for s in DeviceType.objects.all()}
    device_types["A5120-24G-PoE+ EI Switch with 2 Interface Slots"] = device_types[
        "JG236A"
    ]
    device_types["A5120-48G-PoE+ EI Switch with 2 Interface Slots"] = device_types[
        "JG237A"
    ]
    device_types["WS-C4500X-16"] = device_types["WS-C4500X-16SFP+"]

    platforms = dict(
        Cisco=Platform.objects.get(name="Cisco IOS"),
        Arista=Platform.objects.get(name="Arista EOS"),
    )

    status = Status.objects.get(slug="active")

    progress = Progress(*Progress.get_default_columns(), MofNCompleteColumn())
    
    with progress:
        for device in progress.track(devices):
            hostname = device["hostname"].partition(".")[0]
            ip = device["ip"]
            device_type = device_types[device["hardware"]]
            site = None
            role = None
            interface_name = "Vlan900"
            for group in device["groups"]:
                group_name = group["name"]
                if group_name == "Distribution Switches":
                    role = DeviceRole.objects.get(name="Distribution Switches")
                    interface_name = "Loopback0"
                elif group_name == "Access Switches":
                    role = DeviceRole.objects.get(name="Access Switches")
                elif group_name == "Classroom Switches":
                    role = DeviceRole.objects.get(name="Classroom Switches")
                elif group_name == "Campus Core Switches":
                    role = DeviceRole.objects.get(name="Core Switches")
                elif group_name == "Data Centre":
                    role = DeviceRole.objects.get(name="Data Centre Switches")
                elif group_name in all_sites:
                    site = all_sites[group_name]
            assert site is not None
            assert role is not None
            platform = platforms.get(device_type.manufacturer.name, None)
            ip, _ = IPAddress.objects.get_or_create(address=f"{ip}/24")
            nautobot_device, _ = Device.objects.get_or_create(
                name=hostname,
                defaults=dict(
                    device_type=device_type,
                    device_role=role,
                    site=site,
                    platform=platform,
                    status=status,
                ),
            )
            intf, _ = nautobot_device.interfaces.get_or_create(
                name=interface_name, defaults=dict(type="virtual", label="Management", mgmt_only=True)
            )
            intf.ip_addresses.add(ip)
            nautobot_device.primary_ip4 = ip
            
            nautobot_device.validated_save()


class Command(BaseCommand):
    help = "Create or update DeviceType entries in the database, from a 'netbox-community/devicetype-library' compatible git repo"

    def handle(self, *args, **options):

        create_devices()


def _debug():
    from collections import defaultdict

    hosts = defaultdict(None)
    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(None)))

    def normalize(name):
        return name.replace(" ", "_").replace("-", "_").replace("&", "and").lower()

    d = fetch_devices_from_librenms()
    for device in d:
        hostname = device["hostname"]
        hosts[hostname] = None
        for group in device["groups"]:
            group_name = normalize(group["name"])
            groups[group_name]["hosts"][hostname] = None

    inv = dict(all=dict(hosts=dict(hosts), children=groups))

    def tr(d):
        if isinstance(d, dict):
            return dict((k, tr(v)) for k, v in d.items())
        elif isinstance(d, list):
            return [tr(v) for v in d]
        else:
            return d

    from uoft_core.yaml import dumps
    from pathlib import Path

    Path("/home/atremblay/.ansible/hosts.yml").write_text(dumps(tr(inv)))
