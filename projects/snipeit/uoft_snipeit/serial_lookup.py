from . import settings
from .api import SnipeITAPI
import sys


def snipe_serial_lookup(serial):
    s = settings()
    api = SnipeITAPI.from_settings(s)
    try:
        asset_id = api.lookup_serial_raw(serial).json()["rows"][0]["id"]
    except IndexError:
        print(f"{serial} does not match any assets.")
        sys.exit()
    print(f"{asset_id:0>5}")
    return {asset_id: 0 > 5}
