import requests
from . import settings
from .api import SnipeITAPI
from .generate import mklabel_generate_label
from .print import system_print_label
import sys
import re


def snipe_batch_provision(names: list[str], model_id: int = None, location_id: int = None): # type: ignore 
    s = settings()
    if model_id is None:
        model_id = s.default_model_id

    api = SnipeITAPI.from_settings(s)

    try:
        user_will_input = True
        maclist = []
        sanitized_names = [line.strip() for line in names]
        while user_will_input:
            for name in sanitized_names:
                mac_addr_raw = input(
                    f"Enter {name}'s MAC to be added to Snipe, enter 'q' to quit:"
                )  # MACs are expected as "111111111111" and will be formatted to "11:11:11:11:11:11" for Snipe.
                mac_addr = ":".join(mac_addr_raw[i : i + 2] for i in range(0, len(mac_addr_raw), 2))
                maclist.append(mac_addr)
                if "q" in mac_addr:
                    user_will_input = False
                    break
                serial = input(f"Enter {name}'s SERIAL to be added to Snipe, enter 'q' to quit:")
                if "q" in serial:
                    user_will_input = False
                    break
                else:
                    asset = api.create_asset(model_id, mac_addr, name, serial)
                    api.checkout_asset(asset, location_id)
                    mklabel_generate_label(asset)
                    system_print_label()
            else:
                print("The following MACs have been provisioned:\n")
                for mac in maclist:
                    print(f"{mac}")
            sys.exit()
    except Exception as error:
        print(f"Error!: {error}")
