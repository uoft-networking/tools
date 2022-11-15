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

    def checkout_asset(self, asset: int, location_id: int) -> None:
        checkout_url = f"https://{self.hostname}/api/v1/hardware/{asset}/checkout"
        status_url = f"https://{self.hostname}/api/v1/hardware/{asset}"
        payload = {
            "checkout_to_type": "location",
            "status_id": 7,
            "assigned_location": location_id,
            "asset_tag": asset,
        }
        headers = self.headers()
        requests.post(checkout_url, json=payload, headers=headers)
        requests.put(status_url, json=payload, headers=headers)

    def headers(self) -> dict:
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "content-type": "application/json",
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> "SnipeITAPI":
        return cls(settings.snipeit_hostname, settings.api_bearer_key.get_secret_value())