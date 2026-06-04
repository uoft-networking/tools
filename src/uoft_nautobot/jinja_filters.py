from django_jinja import library



@library.filter
def config_path(obj):
    "returns an ideal file path to store the rendered/backed-up config for a given object"
    folder_name = "device-location-missing"
    if obj.location:
        if obj.location.location_type.name == "Building":
            building = obj.location
        else:
            building = obj.location.parent
        folder_name = building.cf["building_code"]
    ext = "txt"
    if obj.platform:
        match obj.platform.network_driver:
            case "arista_eos":
                ext = "eos.cfg"
            case "cisco_ios":
                ext = "ios.cfg"
            case "aruba_aoscx":
                ext = "aoscx.cfg"
            case "cisco_nxos":
                ext = "nxos.cfg"
            case "cisco_xr":
                ext = "iosxr.cfg"
            case "juniper_junos":
                ext = "junos.cfg"
            case "vyos":
                ext = "vyos.cfg"
            case _:
                ext = "txt"

    return f"{folder_name}/{obj.name}.{ext}"

