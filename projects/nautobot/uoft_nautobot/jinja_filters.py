from nautobot.extras.models import Secret
from django_jinja import library

from netaddr import IPNetwork
from box import Box


@library.filter
def combine_with(list_one: list, *other_lists: list):
    "combine multiple lists into a single list"
    res = list_one.copy()
    for l in other_lists:
        res.extend(l)
    return res


@library.filter
def sort_interfaces(intf_list):
    """
    takes a list of interfaces, and returns an equivalent list, 
    sorted to match the order that interfaces show up in a cisco 
    `show run` config backup
    """
    d = {
        "Loopback" : [],
        "Port-channel" : [],
        "GigabitEthernet" : [],
        "TenGigabitEthernet1" : [],
        "FortyGigabitEthernet1" : [],
        "other" : [],
    }
    for i in intf_list:
        for k in d:
            if i.name.startswith(k):
                d[k].append(i)
                break
        else:
            d["other"].append(i)
    res = []
    for l in d.values():
        res.extend(l)
    return res


@library.filter
def except_vlan(vlans: list, exc: int):
    "take a list of VLANs and return an equivalent list with a single VLAN filtered out"
    for vlan in vlans:
        if vlan.vid != exc:
            yield vlan


@library.filter
def uplinks(interfaces):
    return list(filter(lambda i: "uplink" in i.label.lower(), interfaces))


@library.filter
def ip_info(intf: list[Box]):
    """
    take a mixed list of ipv4 and ipv6 addresses,
    and convert it into a box with two attributes, 'v4' and 'v6',
    each of which contain a list of `netaddr.IPNetwork objects
    """
    res = Box(v4=[], v6=[])
    for addr in intf:
        addr = IPNetwork(addr.address)
        if addr.version == 4:
            res.v4.append(addr)
        else:
            res.v6.append(addr)
    return res


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
def vlan_ip_info(vlan: Box):
    """
    convert a `Box(ipv4: dict,ipv6: dict)` object into 
    a `Box(v4: netaddr.IPNetwork, v6: netaddr.IPNetwork)` object
    """
    res = Box(dict(v4=None, v6=None))
    if vlan.ipv4:
        res.v4 = IPNetwork(vlan.ipv4[0].prefix)
    if vlan.ipv6:
        res.v6 = IPNetwork(vlan.ipv6[0].prefix)
    return res


@library.filter
def analyze_obj(obj):
    return obj


@library.filter
def convert_to_IS_id(ipv4: str):
    "take an ip address str and create an ISIS network ID out of it"
    a, b, _, c = ipv4.split(".")
    return f"49.0000.{a:04}.{b:04}.{c:0>4}.00"


@library.filter
def sla_info(vlans):
    count = 1
    for vlan in vlans:
        ip = vlan_ip_info(vlan)
        if ip.v4:
            if vlan.vid == 100:
                # UTSG SLA
                yield Box(
                    dict(
                        num=count,
                        source=dict(ip=ip.v4[1], name=vlan.name),
                        target=dict(ip="128.100.100.123", name="UTSG"),
                    )
                )
                count += 1

            if ip.v4.is_unicast() and not ip.v4.is_private():
                # GOOGLEV4 SLA
                yield Box(
                    dict(
                        num=count,
                        source=dict(ip=ip.v4[1], name=vlan.name),
                        target=dict(ip="8.8.8.8", name="GOOGLEV4"),
                    )
                )
                count += 1
        if ip.v6:
            # GOOGLEV4 SLA
            yield Box(
                dict(
                    num=count,
                    source=dict(ip=ip.v6[1], name=vlan.name),
                    target=dict(ip="2001:4860:4860::8888", name="GOOGLEV6"),
                )
            )
            count += 1
