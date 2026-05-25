from . import settings
from .api import SnipeITAPI
import sys


def snipe_location_lookup(building_code):
    s = settings()
    api = SnipeITAPI.from_settings(s)
    locations = api.lookup_locations_raw().json()["rows"]
    location = next((location for location in locations if location["name"] == f"{building_code}"), None)
    if location is None:
        print(f"No match found.\n")
        sys.exit()
    print(location["id"])
