import requests
from . import settings
from uoft_snipeit import Settings
from uoft_core.prompt import Prompt


class checkout_config:
    def checkout_url(self, asset):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware/{asset}/checkout"

    def status_url(self, asset):
        return f"https://{settings().snipeit_hostname}/api/v1/hardware/{asset}"

    def payload(self, assigned_location, asset):
        return {
            "checkout_to_type": "location",
            "status_id": 7,
            "assigned_location": int(f"{assigned_location}"),
            "asset_tag": int(f"{asset}"),
        }


class checkout_settings:
    def assigned_location(self):
        s = Settings.from_cache()
        history_path = s.util.history_cache
        prompt = Prompt(history_path)
        location = ["150"]  # TODO make this dynamic by looking up the locations.
        print("Select a location to deploy to:\n150 = MN")
        users_location_choice = prompt.get_from_choices("option", location, description="Which location to use?")
        return users_location_choice


def snipe_checkout_asset(asset: int):
    checkout_url = checkout_config().checkout_url(asset)
    status_url = checkout_config().status_url(asset)
    payload = checkout_config().payload(checkout_settings().assigned_location(), asset)
    headers = settings().headers()
    print(f"Asset {asset} checkout:")
    print(requests.post(checkout_url, json=payload, headers=headers))
    print(requests.put(status_url, json=payload, headers=headers))
