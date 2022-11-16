from . import settings
from .api import SnipeITAPI


def snipe_checkout_asset(asset: int, location_id: int = None): # type: ignore
    s = settings()
    
    api = SnipeITAPI.from_settings(s)
    print(f"Asset {asset} checkout:")
    api.checkout_asset(asset, location_id)
