import requests
import re
from . import Settings


class SnipeITAPI:
    def __init__(self, hostname: str, token: str):
        self.hostname = hostname
        self.token = token

    def create_asset(self, model_id: int, mac_addr: str, name: str, serial: str) -> int:
        create_url = f"https://{self.hostname}/api/v1/hardware"
        payload = {
            "status_id": 2,
            "model_id": model_id,
            "_snipeit_mac_address_1": mac_addr,
            "name": name,
            "serial": serial,
        }
        headers = self.headers()
        response = requests.post(create_url, json=payload, headers=headers)
        asset_search = re.findall('"asset_tag":"([^"]+)"', str(response.text))
        asset = asset_search[0]
        return asset

    def checkout_asset(self, asset: int, location_id: int, name: str | None):
        checkout_url = f"https://{self.hostname}/api/v1/hardware/{asset}/checkout"
        status_url = f"https://{self.hostname}/api/v1/hardware/{asset}"
        asset_tag = f"{asset:0>5}"
        payload = {
            "checkout_to_type": "location",
            "status_id": 7,
            "assigned_location": location_id,
            "asset_tag": asset_tag,
            "name": name,
        }
        headers = self.headers()
        r = requests.post(checkout_url, json=payload, headers=headers)
        data = r.json()
        if "status" in data and data["status"] == "error":
            raise Exception(f'{data["messages"]}')
        r = requests.put(status_url, json=payload, headers=headers)
        data = r.json()
        if "status" in data and data["status"] == "error":
            raise Exception(f'{data["messages"]}')

    def lookup_locations_raw(self):
        query_url = f"https://{self.hostname}/api/v1/locations"
        headers = self.headers()
        locations = requests.get(query_url, headers=headers)
        return locations

    def lookup_serial_raw(self, serial):
        query_url = f"https://{self.hostname}/api/v1/hardware/byserial/{serial}"
        headers = self.headers()
        device = requests.get(query_url, headers=headers)
        return device

    def lookup_asset_raw(self, id):
        query_url = f"https://{self.hostname}/api/v1/hardware/{id}"
        headers = self.headers()
        device = requests.get(query_url, headers=headers)
        return device

    def headers(self) -> dict:
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "content-type": "application/json",
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> "SnipeITAPI":
        return cls(settings.snipeit_hostname, settings.api_bearer_key.get_secret_value())
