from . import settings
from .api import SnipeITAPI
from uoft_core.prompt import Prompt


def snipe_checkout_asset(asset: int, location_id: int | None, name: str | None):  # type: ignore
    s = settings()
    api = SnipeITAPI.from_settings(s)
    locations = {location["name"]: location["id"] for location in api.lookup_locations_raw().json()["rows"]}
    if name is None:
        name = api.lookup_asset_raw(asset).json()["name"]
    if location_id is None:
        prompt = Prompt(s.util.history_cache)
        location_names = list(locations.keys())
        location_name = prompt.get_from_choices(
            "Location name to be checked out to", location_names, description=""
        )  # description can be removed once made optional.
        location_id: int = locations[location_name]
    alpha_id = {value: key for key, value in locations.items()}[location_id]
    api.checkout_asset(asset, location_id, name)
    print(f"Asset {name} ID:{asset:0>5} checked out to {alpha_id}.")
