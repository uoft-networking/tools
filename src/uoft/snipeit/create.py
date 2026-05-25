from . import settings
from .api import SnipeITAPI


def snipe_create_asset(mac_addr_raw: str, name: str, serial: str, model_id: int | None = None) -> int:  # type: ignore
    s = settings()
    api = SnipeITAPI.from_settings(s)
    mac_addr = ":".join(mac_addr_raw[i : i + 2] for i in range(0, len(mac_addr_raw), 2))
    assert model_id
    asset = api.create_asset(model_id, mac_addr, name, serial)
    print(f"New asset ID is {asset:0>5}.")
    return asset
