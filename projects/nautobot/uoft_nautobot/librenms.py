from uoft_core import debug_cache, shell

from librenms_handler.devices import Devices
from librenms_handler.device_groups import DeviceGroups
from librenms_handler.switching import Switching

url = "https://librenms.server.utsc.utoronto.ca"


@debug_cache
def get_data():
    token = shell("pass librenms-api")

    ld = Devices(url, token)
    #ldg = DeviceGroups(url, token)
    ls = Switching(url, token)

    devices = ld.list_devices(order_type="up").json()["devices"]
    for d in devices:
        res = ld.get_device_groups(d["device_id"]).json()
        if "groups" in res:
            d["groups"] = res["groups"]
        else:
            d["groups"] = []
        try:
            d["ip_addresses"] = ld.get_device_ip_addresses(d["device_id"]).json()[
                "addresses"
            ]
        except KeyError:
            pass
        try:
            d["links"] = ls.get_links(d["device_id"]).json()["links"]
        except KeyError:
            pass
        try:
            d["vlans"] = ls.get_vlans(d["device_id"]).json()["vlans"]
        except KeyError:
            pass

    return devices

def _debug():
    from collections import defaultdict

    hosts = defaultdict(None)
    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(None)))

    def normalize(name):
        return name.replace(" ", "_").replace("-", "_").replace("&", "and").lower()

    d = get_data()
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
