from uoft_core import debug_cache, shell

from librenms_handler.devices import Devices
from librenms_handler.device_groups import DeviceGroups
from librenms_handler.switching import Switching

url = "https://librenms.server.utsc.utoronto.ca"


@debug_cache
def get_data():
    token = shell("pass librenms-api")

    ld = Devices(url, token)
    # ldg = DeviceGroups(url, token)
    ls = Switching(url, token)

    devices = ld.list_devices(order_type="up").json()["devices"]
    for d in devices:
        d["groups"] = ld.get_device_groups(d["device_id"]).json()["groups"]
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
