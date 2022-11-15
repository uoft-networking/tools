import requests
import re
from . import settings


class create_config:
    def payload(self, model_id, mac_addr, name, serial):
        return {
            "status_id": 2,
            "model_id": int(f"{model_id}"),
            "_snipeit_mac_address_1": f"{mac_addr}",
            "name": f"{name}",
            "serial": f"{serial}",
        }

    def create_url(self):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware"


def snipe_create_asset(mac_addr: str, name: str, serial: str, model_id: int = None) -> int:  # type: ignore
    s = settings()
    if model_id is None:
        model_id = s.default_model_id

    create_url = create_config().create_url()
    payload = create_config().payload(model_id, mac_addr, name, serial)
    headers = s.headers()
    response = requests.post(create_url, json=payload, headers=headers)
    asset_search = re.findall('"asset_tag":"([^"]+)"', str(response.text))
    asset = asset_search[0]
    print(f"{response}\nNew asset ID is {asset}.")
    return asset
