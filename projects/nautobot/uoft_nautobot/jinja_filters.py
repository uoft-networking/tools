from textwrap import indent, dedent
from django_jinja import library

from netaddr import IPNetwork
from box import Box
from .golden_config import Interface, Room, Building, DistributionSwitch, VLAN


@library.filter
def combine_with(list_one: list, *other_lists: list):
    "combine multiple lists into a single list"
    res = list_one.copy()
    for l in other_lists:
        res.extend(l)
    return res


@library.filter
def reindent(text: str, spaces: int):
    "reindent a block of text"
    return indent(dedent(str(text)), " " * spaces)


@library.filter
def except_vlan(vlans: list[VLAN], exc: int):
    "take a list of VLANs and return an equivalent list with a single VLAN filtered out"
    for vlan in vlans:
        if vlan.vid != exc:
            yield vlan


@library.filter
def uplinks(interfaces: list[Interface]):
    return [i for i in interfaces if i.type == "uplink"]


@library.filter
def allowed_vlans(native_vlan: int):
    """
    for a given native vlan, return a string containing a 
    cisco-style range of all vlans excluding this native vlan"""
    match native_vlan:
        case 1:
            return "2-4094"
        case 2:
            return "3-4094"
        case 4093:
            return "2-4092,4094"
        case 4094:
            return "2-4093"
        case _:
            return f"2-{native_vlan-1},{native_vlan+1}-4094"


@library.filter
def analyze_obj(obj):
    return obj


@library.filter
def convert_to_IS_id(ipv4: str):
    "take an ip address str and create an ISIS network ID out of it"
    a, b, _, c = ipv4.split(".")
    return f"49.0000.{a:04}.{b:04}.{c:0>4}.00"


@library.filter
def sla_info(vlans: list[VLAN]):
    count = 1
    for vlan in vlans:
        if vlan.ip_v4:
            if vlan.vid == 100:
                # UTSG SLA
                yield Box(
                    dict(
                        num=count,
                        source=dict(ip=vlan.ip_v4[1], name=vlan.name),
                        target=dict(ip="128.100.100.123", name="UTSG"),
                    )
                )
                count += 1

            if vlan.ip_v4.is_unicast() and not vlan.ip_v4.is_private():
                # GOOGLEV4 SLA
                yield Box(
                    dict(
                        num=count,
                        source=dict(ip=vlan.ip_v4[1], name=vlan.name),
                        target=dict(ip="8.8.8.8", name="GOOGLEV4"),
                    )
                )
                count += 1
        if vlan.ip_v6:
            # GOOGLEV4 SLA
            yield Box(
                dict(
                    num=count,
                    source=dict(ip=vlan.ip_v6[1], name=vlan.name),
                    target=dict(ip="2001:4860:4860::8888", name="GOOGLEV6"),
                )
            )
            count += 1
