from .create import snipe_create_asset
from .checkout import snipe_checkout_asset


def snipe_create_checkout(mac_addr: str, name: str, serial: str):
    asset = snipe_create_asset(mac_addr, name, serial)
    snipe_checkout_asset(asset)
    return asset
