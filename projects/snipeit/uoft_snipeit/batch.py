import requests
from . import settings
from uoft_snipeit import Settings
from uoft_core.prompt import Prompt
from .generate import mklabel_generate_label
from .print import system_print_label
import sys
import re


def snipe_batch_provision(names: list[str]):
    bs_model_id = batch_settings().model_id()
    bs_assigned_location = batch_settings().assigned_location()

    def batch_create_asset(mac_addr: str, name: str, serial: str):
        create_url = batch_config().create_url()
        payload = batch_config().create_payload(bs_model_id, mac_addr, name, serial)
        headers = settings().headers()
        response = requests.post(create_url, json=payload, headers=headers)
        asset_search = re.findall('"asset_tag":"([^"]+)"', str(response.text))
        asset = asset_search[0]
        print(f"{response}\nNew asset ID is {asset}.")
        return asset

    def batch_checkout_asset(asset: int):
        checkout_url = batch_config().checkout_url(asset)
        status_url = batch_config().status_url(asset)
        payload = batch_config().checkout_payload(bs_assigned_location, asset)
        headers = settings().headers()
        print(f"Asset {asset} checkout:")
        print(requests.post(checkout_url, json=payload, headers=headers))
        print(requests.put(status_url, json=payload, headers=headers))

    try:
        user_will_input = True
        maclist = []
        sanitized_names = [line.strip() for line in names]
        while user_will_input:
            for name in sanitized_names:
                mac_addr_raw = input(
                    f"Enter {name}'s MAC to be added to Snipe, enter 'q' to quit:"
                )  # MACs are expected as "111111111111" and will be formatted to "11:11:11:11:11:11" for Snipe.
                mac_addr = ":".join(mac_addr_raw[i : i + 2] for i in range(0, len(mac_addr_raw), 2))
                maclist.append(mac_addr)
                if "q" in mac_addr:
                    user_will_input = False
                    break
                serial = input(f"Enter {name}'s SERIAL to be added to Snipe, enter 'q' to quit:")
                if "q" in serial:
                    user_will_input = False
                    break
                else:
                    asset = batch_create_asset(mac_addr, name, serial)
                    batch_checkout_asset(asset)
                    mklabel_generate_label(asset)
                    system_print_label()
            else:
                print("The following MACs have been provisioned:\n")
                for mac in maclist:
                    print(f"{mac}")
            sys.exit()
    except Exception as error:
        print(f"Error!: {error}")


class batch_config:
    def create_payload(self, model_id, mac_addr, name, serial):
        return {
            "status_id": 2,
            "model_id": int(f"{model_id}"),
            "_snipeit_mac_address_1": f"{mac_addr}",
            "name": f"{name}",
            "serial": f"{serial}",
        }

    def create_url(self):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware"

    def checkout_url(self, asset):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware/{asset}/checkout"

    def status_url(self, asset):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware/{asset}"

    def checkout_payload(self, assigned_location, asset):
        return {
            "checkout_to_type": "location",
            "status_id": 7,
            "assigned_location": int(f"{assigned_location}"),
            "asset_tag": int(f"{asset}"),
        }


class batch_settings:
    def model_id(self) -> int:
        s = Settings.from_cache()
        history_path = s.util.history_cache
        prompt = Prompt(history_path)
        model = ["138"]  # TODO make this dynamic by looking up the models.
        print("138 = ARUBA AP-535 (RW) UNIFIED AP\n")
        users_model_choice = prompt.get_from_choices("option", model, description="Which model to use?")
        return int(users_model_choice)

    def assigned_location(self):
        s = Settings.from_cache()
        history_path = s.util.history_cache
        prompt = Prompt(history_path)
        location = ["150"]  # TODO make this dynamic by looking up the locations.
        print("Select a location to deploy to:\n150 = MN")
        users_location_choice = prompt.get_from_choices("option", location, description="Which location to use?")
        return users_location_choice
