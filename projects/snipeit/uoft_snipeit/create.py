from . import settings
from .api import SnipeITAPI


def snipe_create_asset(mac_addr: str, name: str, serial: str, model_id: int = None) -> int:  # type: ignore
    s = settings()
    if model_id is None:
        model_id = s.default_model_id
    
    api = SnipeITAPI.from_settings(s)
    asset = api.create_asset(model_id, mac_addr, name, serial)
    print(f"New asset ID is {asset}.")
    return asset
