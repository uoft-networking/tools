from . import settings
from .api import phpIPAMRESTAPIClient
import sys


def phpipam_serial_lookup(serial) -> dict:
    s = settings()
    with (phpIPAMRESTAPIClient(s.hostname, s.username, s.password.get_secret_value(), s.app_id) as host):

        devices = host.get_all_addresses_raw().json()["data"]
        device_info = next((device for device in devices if device["custom_Serial"] == f"{serial}"), None)
        if device_info is None:
            print(f"No match found.\n")
            sys.exit()
        return device_info
