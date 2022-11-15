from . import settings
from .api import SnipeITAPI


def snipe_checkout_asset(asset: int, location_id: int = None): # type: ignore
    s = settings()
    if location_id is None:
        location_id = s.default_assigned_location_id
    
    api = SnipeITAPI.from_settings(s)
    print(f"Asset {asset} checkout:")
    api.checkout_asset(asset, location_id)
