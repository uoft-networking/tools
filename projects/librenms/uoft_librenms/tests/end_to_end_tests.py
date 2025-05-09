from .. import Settings
import typing as t
import pytest
from pathlib import Path
from uoft_core._vendor.dict_typer import get_type_definitions

fixtures_dir = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def vcr_config():
    return dict(
        filter_headers=["X-Auth-Token"],
        record_mode="once",
        cassette_library_dir=str(fixtures_dir / "_private/cassettes"),
    )


@pytest.mark.end_to_end
@pytest.mark.vcr(record_mode="new_episodes")
@pytest.mark.default_cassette("LibreNMS.default.yaml")
class LibreNMSTests:
    @t.no_type_check
    def test_discovery(self):
        s = Settings.from_cache()
        api = s.api_connection()
        res = "from typing import List, Optional, Union, TypedDict"

        data = api.devices.list_devices()
        res += get_type_definitions(
            data, "Devices", name_map={"DevicesItem0": "Device"}
        )
        res += "\n\n"

        data = api.ports.get_port_info(1)
        res += get_type_definitions(data, "Ports", name_map={"PortItem0": "Port"})
        res += "\n\n"

        data = api.ports.get_port_ip_info(45526)
        res += get_type_definitions(
            data, "PortIPs", name_map={"AddressesItem0": "PortIP"}
        )
        res += "\n\n"

        data = api.device_groups.get_devicegroups()
        res += get_type_definitions(
            data,
            "DeviceGroups",
            name_map={
                "GroupsItem0": "DeviceGroup",
                "Rules": "DynamicGroupRules",
                "RulesItem0": "DynamicGroupRule",
            },
        )
        res += "\n\n"

        data = api.devices.get_components("d1-aa.netmgmt.utsc.utoronto.ca")
        data["components"] = list(data["components"].values())
        res += get_type_definitions(
            data, "Components", name_map={"ComponentsItem0": "Component"}
        )
        res += "\n\n"

        data = api.switching.list_vlans()
        res += get_type_definitions(data, "Vlans", name_map={"VlansItem0": "Vlan"})
        res += "\n\n"

        data = api.switching.list_links()
        res += get_type_definitions(data, "Links", name_map={"LinksItem0": "Link"})
        res += "\n\n"

        print(res)
        print()

