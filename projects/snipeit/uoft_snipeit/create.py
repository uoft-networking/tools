import requests
import re
from . import settings
from uoft_snipeit import Settings
from uoft_core.prompt import Prompt


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


class create_settings:
    def model_id(self):
        s = Settings.from_cache()
        history_path = s.util.history_cache
        prompt = Prompt(history_path)
        model = ["138"]  # TODO make this dynamic by looking up the models.
        print("138 = ARUBA AP-535 (RW) UNIFIED AP\n")
        users_model_choice = prompt.get_from_choices("option", model, description="Which model to use?")
        return users_model_choice


def snipe_create_asset(mac_addr: str, name: str, serial: str):
    create_url = create_config().create_url()
    payload = create_config().payload(create_settings().model_id(), mac_addr, name, serial)
    headers = settings().headers()
    response = requests.post(create_url, json=payload, headers=headers)
    asset_search = re.findall('"asset_tag":"([^"]+)"', str(response.text))
    asset = asset_search[0]
    print(f"{response}\nNew asset ID is {asset}.")
    return asset
