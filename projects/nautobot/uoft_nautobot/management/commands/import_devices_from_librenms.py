from django.core.management.base import BaseCommand
from uoft_core import debug_cache, shell
from uoft_librenms import Settings

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
    s = Settings.from_cache()
    api = s.api_connection()
    devices = api.devices.list_devices()['devices']
    ports = api.ports.get_all_ports(columns=[
                "port_id",
                "device_id",
                "ifIndex",
                "ifName",
                "ifAlias",
                "ifDescr",
                "ifOperStatus",
                "ifAdminStatus",
                "ifType",
                "ifVlan",
                "ifTrunk",
                "disabled",
            ])['ports']
    device_groups = api.device_groups.get_devicegroups()['groups']
    vlans = api.switching.list_vlans()['vlans']
    links = api.switching.list_links()["links"]
    res = {d['device_id']: d for d in devices}
    for d in res.values():
        d["ports"] = []
        d['groups'] = []
        d['vlans'] = []
        d['links'] = []
    for p in ports:
        device_id = p['device_id']
        if device_id in res:
            res[device_id]['ports'].append(p)
        del device_id
    for g in device_groups:
        for d in api.device_groups.get_devices_by_group(g['id'])['devices']:
            device_id = d['device_id']
            if device_id in res:
                res[device_id]['groups'].append(g)
            del device_id
    for v in vlans:
        device_id = v['device_id']
        if device_id in res:
            res[device_id]['vlans'].append(v)
        del device_id
    for l in links:
        device_id = l['local_device_id']
        if device_id in res:
            res[device_id]['links'].append(l)
        del device_id

    return res

ALL_SITES = {}
DEVICE_TYPES = {}
PLATFORMS = {}
STATUS = None

def create_device(device: dict):
    hostname = device["hostname"].partition(".")[0]
    ip = device["ip"]
    device_type = DEVICE_TYPES[device["hardware"]]
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
        elif group_name in ALL_SITES:
            site = ALL_SITES[group_name]
    assert site is not None
    assert role is not None
    platform = PLATFORMS.get(device_type.manufacturer.name, None)
    ip, _ = IPAddress.objects.get_or_create(address=f"{ip}/24")
    nautobot_device, _ = Device.objects.get_or_create(
        name=hostname,
        defaults=dict(
            device_type=device_type,
            device_role=role,
            site=site,
            platform=platform,
            status=STATUS,
        ),
    )
    intf, _ = nautobot_device.interfaces.get_or_create(
        name=interface_name, defaults=dict(type="virtual", label="Management", mgmt_only=True)
    )
    intf.ip_addresses.add(ip)
    nautobot_device.primary_ip4 = ip
    
    nautobot_device.validated_save()


def create_devices():
    devices = fetch_devices_from_librenms()

    ALL_SITES = {s.name: s for s in Site.objects.all()}
    ALL_SITES["Student Life"] = ALL_SITES["Student Centre"]
    ALL_SITES["Environment Sciences & Chemistry Building"] = ALL_SITES[
        "Environmental Science & Chemistry Building"
    ]

    DEVICE_TYPES = {s.part_number: s for s in DeviceType.objects.all()}
    DEVICE_TYPES["A5120-24G-PoE+ EI Switch with 2 Interface Slots"] = DEVICE_TYPES[
        "JG236A"
    ]
    DEVICE_TYPES["A5120-48G-PoE+ EI Switch with 2 Interface Slots"] = DEVICE_TYPES[
        "JG237A"
    ]
    DEVICE_TYPES["WS-C4500X-16"] = DEVICE_TYPES["WS-C4500X-16SFP+"]

    PLATFORMS = dict(
        Cisco=Platform.objects.get(name="Cisco IOS"),
        Arista=Platform.objects.get(name="Arista EOS"),
    )

    STATUS = Status.objects.get(slug="active")

    progress = Progress(*Progress.get_default_columns(), MofNCompleteColumn())
    
    with progress:
        for device in progress.track(devices):
            create_device(device)


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
