import requests
from . import settings


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


def snipe_checkout_asset(asset: int, location_id: int = None): # type: ignore
    s = settings()
    if location_id is None:
        location_id = s.default_assigned_location_id
    
    checkout_url = checkout_config().checkout_url(asset)
    status_url = checkout_config().status_url(asset)
    payload = checkout_config().payload(location_id, asset)
    headers = s.headers()
    print(f"Asset {asset} checkout:")
    print(requests.post(checkout_url, json=payload, headers=headers))
    print(requests.put(status_url, json=payload, headers=headers))
