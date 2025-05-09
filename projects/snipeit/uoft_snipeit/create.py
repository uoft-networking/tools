from . import settings
from .api import SnipeITAPI


def snipe_create_asset(mac_addr: str, name: str, serial: str, model_id: int) -> int:  # type: ignore
    s = settings()

    api = SnipeITAPI.from_settings(s)
    asset = api.create_asset(model_id, mac_addr, name, serial)
    print(f"New asset ID is {asset:0>5}.")
    return asset
